import sys
import os
import ast
import importlib
import subprocess
from PyQt6 import uic
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QListWidget, QListWidgetItem, QPushButton, QMessageBox
)
from PyQt6.QtGui import QPixmap, QPainter, QColor, QIcon
from PyQt6.QtCore import QSize, Qt, QProcess, QTimer, QProcessEnvironment

MODULE_PKG_MAP = {
    "PIL": "pillow",
    "Pillow": "pillow",
    "cv2": "opencv-python",
    "skimage": "scikit-image",
    "yaml": "pyyaml",
    "PILLOW": "pillow",
}

STANDARD_LIB_CACHE = None

def is_stdlib(mod_name: str):
    import importlib.util
    global STANDARD_LIB_CACHE
    # Cache léger
    if STANDARD_LIB_CACHE is None:
        STANDARD_LIB_CACHE = set()
    try:
        spec = importlib.util.find_spec(mod_name)
    except Exception:
        return False
    if spec is None:
        return False
    origin = spec.origin or ""
    # Heuristique: stdlib (sans site-packages)
    return "site-packages" not in origin.lower()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        ui_path = os.path.join(os.path.dirname(__file__), "ui", "main_window.ui")
        print(f"[DEBUG] Chemin UI utilisé: {ui_path} (existe={os.path.isfile(ui_path)})")
        if not os.path.isfile(ui_path):
            raise FileNotFoundError(f"UI introuvable: {ui_path}")
        uic.loadUi(ui_path, self)

        # Debug: lister tous les objectName chargés
        from PyQt6.QtWidgets import QWidget
        loaded_names = [w.objectName() for w in self.findChildren(QWidget)]
        print("[DEBUG] Noms trouvés dans l'UI:", loaded_names)

        # Accès direct (uic.loadUi crée déjà les attributs)
        self.treeScripts = getattr(self, "treeScripts", None)
        self.searchLine = getattr(self, "lineEdit", None)
        self.tabWidget = getattr(self, "tabWidget", None)
        self.activeScriptsList = getattr(self, "listWidget", None)

        missing = [
            name for name, ref in {
                "treeScripts": self.treeScripts,
                "lineEdit": self.searchLine,
                "tabWidget": self.tabWidget,
                "listWidget": self.activeScriptsList,
            }.items() if ref is None
        ]
        if missing:
            print(f"[ERREUR] Widgets manquants: {missing}")
            # Pour éviter de tout casser, on sort proprement.
            return

        self.searchLine.setPlaceholderText("Rechercher")
        self.searchLine.textChanged.connect(self.filter_tree)

        self.tabWidget.setTabsClosable(True)
        self.tabWidget.tabCloseRequested.connect(self.close_tab)
        self.activeScriptsList.itemClicked.connect(self.goto_tab)

        self.tab_status = {}  # {script_name: status}
        self.processes = {}
        self.script_editors = {}   # (on le garde si utilisé ailleurs)
        self.script_outputs = {}   # script_name -> QTextEdit (console)
        self.input_lines = {}      # script_name -> QLineEdit

        # Charger automatiquement les scripts depuis le dossier scripts/
        self.load_scripts_from_folder()

    # --------------------------
    # Charger les scripts dynamiquement
    # --------------------------
    def load_scripts_from_folder(self):
        self.treeScripts.clear()
        self.treeScripts.setColumnCount(1)
        self.treeScripts.setHeaderLabel("Scripts")
        self.treeScripts.setRootIsDecorated(True)
        self.treeScripts.setIndentation(16)

        scripts_root = os.path.join(os.path.dirname(__file__), "scripts")
        print(f"[DEBUG] Scan dossier scripts: {scripts_root}")
        if not os.path.isdir(scripts_root):
            print("Dossier 'scripts' introuvable.")
            return

        categories_trouvees = 0
        fichiers_total = 0

        for category_name in sorted(os.listdir(scripts_root)):
            category_path = os.path.join(scripts_root, category_name)
            if not os.path.isdir(category_path):
                continue
            categories_trouvees += 1
            cat_item = QTreeWidgetItem([category_name])
            self.treeScripts.addTopLevelItem(cat_item)

            # Fichiers acceptés: .py ou sans extension
            scripts = []
            for f in sorted(os.listdir(category_path)):
                full = os.path.join(category_path, f)
                if os.path.isfile(full):
                    if f.endswith(".py"):
                        scripts.append((os.path.splitext(f)[0], full))
                    elif "." not in f:  # fichier sans extension
                        scripts.append((f, full))
            print(f"[DEBUG] Catégorie '{category_name}' -> {len(scripts)} script(s) détecté(s)")

            for script_name, full_path in scripts:
                fichiers_total += 1
                child = QTreeWidgetItem([script_name])
                child.setData(0, Qt.ItemDataRole.UserRole, full_path)
                cat_item.addChild(child)

            if cat_item.childCount() > 0:
                cat_item.setExpanded(True)

        print(f"[DEBUG] Résumé: catégories={categories_trouvees}, scripts_detectes={fichiers_total}")

        try:
            self.treeScripts.itemClicked.disconnect()
        except Exception:
            pass
        self.treeScripts.itemClicked.connect(self.on_item_clicked)

        if fichiers_total == 0:
            print("[INFO] Aucun script détecté. Vérifie extensions (.py) ou noms de fichiers.")

    # Option récursive si besoin (appelle à la place du bloc non récursif ci-dessus)
    def _add_scripts_recursive(self, parent_item, base_path):
        import os
        for entry in sorted(os.listdir(base_path)):
            p = os.path.join(base_path, entry)
            if os.path.isdir(p):
                sub_item = QTreeWidgetItem([entry])
                parent_item.addChild(sub_item)
                self._add_scripts_recursive(sub_item, p)
                if sub_item.childCount() == 0:
                    # Retirer dossiers vides
                    parent_item.removeChild(sub_item)
            elif entry.endswith(".py"):
                script_name = os.path.splitext(entry)[0]
                QTreeWidgetItem(parent_item, [script_name])

    # --------------------------
    # Filtrage
    # --------------------------
    def filter_tree(self, text):
        text = text.lower()
        for i in range(self.treeScripts.topLevelItemCount()):
            category = self.treeScripts.topLevelItem(i)
            has_visible_child = False
            for j in range(category.childCount()):
                script = category.child(j)
                match = text in script.text(0).lower()
                script.setHidden(not match)
                if match:
                    has_visible_child = True
            category.setHidden(not has_visible_child)

    # --------------------------
    # Gestion des onglets
    # --------------------------
    def on_item_clicked(self, item, column):
        if not item.parent():
            return
        script_name = item.text(0)
        full_path = item.data(0, Qt.ItemDataRole.UserRole)
        category_name = item.parent().text(0)

        for i in range(self.tabWidget.count()):
            if self.tabWidget.tabText(i) == script_name:
                self.tabWidget.setCurrentIndex(i)
                return

        new_tab = QWidget()
        layout = QVBoxLayout()

        # Vue code (lecture seule)
        code_view = QTextEdit()
        code_view.setReadOnly(True)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                code_view.setPlainText(f.read())
        except Exception as e:
            code_view.setPlainText(f"Erreur lecture fichier: {e}")
        layout.addWidget(code_view)

        # Console de sortie
        output_box = QTextEdit()
        output_box.setReadOnly(True)
        output_box.setPlaceholderText("Sortie du script...")
        layout.addWidget(output_box)

        # Barre de boutons
        button_layout = QHBoxLayout()
        play_button = QPushButton("Play")
        stop_button = QPushButton("Stop")
        button_layout.addWidget(play_button)
        button_layout.addWidget(stop_button)
        layout.addLayout(button_layout)

        # Ligne d'entrée + bouton envoyer
        input_layout = QHBoxLayout()
        input_line = QLineEdit()
        input_line.setPlaceholderText("Entrée pour le script (appuie Entrée ou Envoyer)")
        send_btn = QPushButton("Envoyer")
        input_layout.addWidget(input_line)
        input_layout.addWidget(send_btn)
        layout.addLayout(input_layout)

        play_button.clicked.connect(lambda _, c=category_name, s=script_name: self.start_script(c, s))
        stop_button.clicked.connect(lambda _, c=category_name, s=script_name: self.stop_script(c, s))
        send_btn.clicked.connect(lambda _, c=category_name, s=script_name: self.send_input(c, s))
        input_line.returnPressed.connect(lambda c=category_name, s=script_name: self.send_input(c, s))

        new_tab.setLayout(layout)
        self.tabWidget.addTab(new_tab, script_name)
        self.tabWidget.setCurrentWidget(new_tab)

        self.tab_status[script_name] = "stop"
        # On conserve script_editors pour compat, mais on stocke la console dans script_outputs
        self.script_editors[script_name] = output_box
        self.script_outputs[script_name] = output_box
        self.input_lines[script_name] = input_line

    def close_tab(self, index):
        tab_name = self.tabWidget.tabText(index)
        self.tabWidget.removeTab(index)
        for i in range(self.activeScriptsList.count()):
            if self.activeScriptsList.item(i).text() == tab_name:
                self.activeScriptsList.takeItem(i)
                break
        if tab_name in self.tab_status:
            del self.tab_status[tab_name]

    def goto_tab(self, item):
        script_name = item.text()
        for i in range(self.tabWidget.count()):
            if self.tabWidget.tabText(i) == script_name:
                self.tabWidget.setCurrentIndex(i)
                break

    # --------------------------
    # Play / Stop / Attente
    # --------------------------
    def start_script(self, category_name, script_name):
        if script_name in self.processes:
            print(f"[INFO] Script déjà en cours: {script_name}")
            return

        script_path = self._resolve_script_path(category_name, script_name)
        if not script_path:
            return

        missing_pkgs = self.collect_missing_packages(script_path)
        if missing_pkgs:
            rep = QMessageBox.question(
                self,
                "Dépendances manquantes",
                "Packages manquants:\n  - " + "\n  - ".join(missing_pkgs) +
                "\n\nInstaller maintenant ?",
            )
            if rep == QMessageBox.StandardButton.Yes:
                self.install_dependencies(missing_pkgs, lambda ok: self._launch_script_after_install(ok, category_name, script_name, script_path))
                return
            else:
                return

        self._launch_script_after_install(True, category_name, script_name, script_path)

    def _launch_script_after_install(self, ok, category_name, script_name, script_path):
        if not ok:
            QMessageBox.warning(self, "Échec", "Installation des dépendances échouée.")
            return
        out = self.script_outputs.get(script_name)
        if out:
            out.clear()
        self.tab_status[script_name] = "en_cours"
        self.add_active_script(script_name, status="en_cours")

        proc = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("KGIS_UTF8", "1")
        proc.setProcessEnvironment(env)

        proc.setProgram(sys.executable)
        proc.setArguments([script_path])
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(lambda s=script_name: self._append_output(s))
        proc.errorOccurred.connect(lambda _err, s=script_name: self._process_error(s))
        proc.finished.connect(lambda code, status, s=script_name: self._script_finished(s, code))
        proc.start()
        self.processes[script_name] = proc
        print(f"[RUN] {script_name} lancé.")

    # --- Détection dépendances ---
    def parse_declared_requirements(self, script_path):
        reqs = []
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                for i in range(15):  # lire seulement début
                    line = f.readline()
                    if not line:
                        break
                    if "requirements:" in line.lower():
                        # ex: # requirements: pillow, opencv-python
                        part = line.split(":", 1)[1]
                        reqs = [r.strip() for r in part.split(",") if r.strip()]
                        break
        except Exception:
            pass
        return reqs

    def collect_missing_packages(self, script_path):
        modules_missing = self.get_missing_dependencies(script_path)  # modules (import)
        declared = self.parse_declared_requirements(script_path)      # packages explicites
        # Map modules -> packages
        pkgs = set(declared)
        for mod in modules_missing:
            pkgs.add(MODULE_PKG_MAP.get(mod, mod))
        # Vérifier si déjà installés
        final_missing = []
        for pkg in sorted(pkgs):
            if not self._package_installed(pkg):
                final_missing.append(pkg)
        return final_missing

    def _package_installed(self, package_name):
        try:
            import importlib.metadata as md
            md.version(package_name)
            return True
        except Exception:
            # fallback simple: tenter import du module racine
            try:
                import importlib
                importlib.import_module(package_name.replace("-", "_"))
                return True
            except Exception:
                return False

    def install_dependencies(self, packages, callback):
        if not packages:
            QTimer.singleShot(0, lambda: callback(True))
            return

        cmd = [sys.executable, "-m", "pip", "install", *packages]
        print("[PIP]", " ".join(cmd))

        pip_proc = QProcess(self)
        pip_proc.setProgram(cmd[0])
        pip_proc.setArguments(cmd[1:])
        pip_proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        # Petite console globale: réutiliser le premier onglet ouvert si dispo
        any_output = next(iter(self.script_outputs.values()), None)
        if any_output:
            any_output.append(f"[INSTALL] pip install {' '.join(packages)}")

        def _append():
            data = pip_proc.readAllStandardOutput().data().decode(errors="replace")
            if any_output and data:
                any_output.append(data.rstrip())

        def _done(code, status):
            ok = (code == 0)
            if any_output:
                any_output.append(f"[INSTALL] Terminé (code={code})")
            callback(ok)

        pip_proc.readyReadStandardOutput.connect(_append)
        pip_proc.finished.connect(_done)
        pip_proc.start()

    def stop_script(self, category_name, script_name):
        proc = self.processes.get(script_name)
        if proc and proc.state() != QProcess.ProcessState.NotRunning:
            proc.kill()
            proc.waitForFinished(1000)
            print(f"[STOP] {script_name} interrompu.")
        self.processes.pop(script_name, None)
        self.tab_status[script_name] = "termine"
        self.update_script_status(script_name, status="termine")

    def send_input(self, category_name, script_name):
        proc = self.processes.get(script_name)
        if not proc or proc.state() == QProcess.ProcessState.NotRunning:
            print("[INFO] Script non démarré ou déjà terminé.")
            return
        line_edit = self.input_lines.get(script_name)
        if not line_edit:
            return
        text = line_edit.text()
        if text == "":
            return
        # Afficher aussi la ligne entrée dans la console (optionnel)
        out = self.script_outputs.get(script_name)
        if out:
            out.append(f"> {text}")
        proc.write((text + "\n").encode("utf-8"))
        line_edit.clear()

    def _append_output(self, script_name):
        proc = self.processes.get(script_name)
        if not proc:
            return
        data = proc.readAllStandardOutput().data().decode(errors="replace")
        box = self.script_outputs.get(script_name)
        if box and data:
            box.append(data.rstrip())

    def _process_error(self, script_name):
        box = self.script_outputs.get(script_name)
        if box:
            box.append("[ERREUR] Process QProcess")

    def _script_finished(self, script_name, exit_code):
        self.processes.pop(script_name, None)
        status = "termine" if exit_code == 0 else "erreur"
        self.tab_status[script_name] = status
        self.update_script_status(script_name, status=status)
        print(f"[END] {script_name} terminé code={exit_code}")

    def _resolve_script_path(self, category_name, script_name):
        for i in range(self.treeScripts.topLevelItemCount()):
            cat = self.treeScripts.topLevelItem(i)
            if cat.text(0) == category_name:
                for j in range(cat.childCount()):
                    ch = cat.child(j)
                    if ch.text(0) == script_name:
                        return ch.data(0, Qt.ItemDataRole.UserRole)
        print("Script introuvable.")
        return None

    def get_missing_dependencies(self, script_path):
        with open(script_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=script_path)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    imports.add(n.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])

        std_ignore = {
            "os","sys","json","pathlib","shutil","glob","ctypes","math","time",
            "subprocess","re","typing","threading","itertools","functools",
            "collections","statistics","argparse","tempfile","random","datetime",
            "inspect","traceback","logging","uuid","queue"
        }

        missing = []
        for mod in sorted(imports):
            if mod in std_ignore:
                continue
            if is_stdlib(mod):
                continue
            try:
                importlib.import_module(mod)
            except ImportError:
                missing.append(mod)
        return missing

    # --------------------------
    # Liste des scripts actifs
    # --------------------------
    def add_active_script(self, script_name, status="en_cours"):
        for i in range(self.activeScriptsList.count()):
            if self.activeScriptsList.item(i).text() == script_name:
                return
        item = QListWidgetItem(script_name)
        item.setIcon(self.create_status_icon(status))
        self.activeScriptsList.addItem(item)

    def update_script_status(self, script_name, status):
        for i in range(self.activeScriptsList.count()):
            item = self.activeScriptsList.item(i)
            if item.text() == script_name:
                item.setIcon(self.create_status_icon(status))
                break

    def create_status_icon(self, status, size=7):
        if status == "en_cours":
            color = QColor("blue")
        elif status == "termine":
            color = QColor("green")
        elif status == "erreur":
            color = QColor("red")
        elif status == "en_attente":
            color = QColor("magenta")
        else:
            color = QColor("gray")

        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        painter.setBrush(color)
        painter.setPen(QColor(0, 0, 0, 0))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawEllipse(0, 0, size, size)
        painter.end()
        return QIcon(pixmap)

    # --------------------------
    # Exécution d’un script
    # --------------------------
    def run_script(self, category_name, script_name):
        # Recherche d’abord via l’arbre (data stockée)
        for i in range(self.treeScripts.topLevelItemCount()):
            cat = self.treeScripts.topLevelItem(i)
            if cat.text(0) == category_name:
                for j in range(cat.childCount()):
                    ch = cat.child(j)
                    if ch.text(0) == script_name:
                        script_path = ch.data(0, Qt.ItemDataRole.UserRole)
                        break
                else:
                    continue
                break
        else:
            print("Script introuvable dans l'arbre.")
            return

        if not os.path.isfile(script_path):
            print(f"Script introuvable: {script_path}")
            return

        import importlib.util
        spec = importlib.util.spec_from_file_location(f"kgis_scripts.{script_name}", script_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
