import sys
from PyQt6 import uic
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QTabWidget, QWidget, QVBoxLayout, QTextEdit
)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("ui/main_window.ui", self)  # Charge le .ui

        # Récupérer les widgets
        self.treeScripts = self.findChild(QTreeWidget, "treeScripts")
        if not self.treeScripts:
            raise ValueError("Le QTreeWidget 'treeScripts' n'a pas été trouvé dans le .ui")

        self.searchLine = self.findChild(QLineEdit, "lineEdit")
        if self.searchLine:
            self.searchLine.setPlaceholderText("Rechercher")
            self.searchLine.textChanged.connect(self.filter_tree)

        self.tabWidget = self.findChild(QTabWidget, "tabWidget")
        if not self.tabWidget:
            raise ValueError("Le QTabWidget 'tabWidget' n'a pas été trouvé dans le .ui")

        # Activer les onglets fermables
        self.tabWidget.setTabsClosable(True)
        self.tabWidget.tabCloseRequested.connect(self.close_tab)

        # Remplir le treeScripts
        self.load_scripts()

    def load_scripts(self):
        # ----------------- Catégorie 1 -----------------
        cat1 = QTreeWidgetItem(self.treeScripts, ["Catégorie 1"])
        cat1.setExpanded(True)
        QTreeWidgetItem(cat1, ["Script A"])
        QTreeWidgetItem(cat1, ["Script B"])

        # ----------------- Catégorie 2 -----------------
        cat2 = QTreeWidgetItem(self.treeScripts, ["Catégorie 2"])
        cat2.setExpanded(True)
        QTreeWidgetItem(cat2, ["Script C"])
        QTreeWidgetItem(cat2, ["Script D"])

        # ----------------- Catégorie 3 -----------------
        cat3 = QTreeWidgetItem(self.treeScripts, ["Catégorie 3"])
        cat3.setExpanded(True)
        QTreeWidgetItem(cat3, ["Script E"])
        QTreeWidgetItem(cat3, ["Script F"])

        # Connecter le clic sur un script
        self.treeScripts.itemClicked.connect(self.on_item_clicked)

    def filter_tree(self, text):
        """Filtre les scripts dans le treeWidget selon le texte entré."""
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

    def on_item_clicked(self, item, column):
        # Si c’est un script (pas une catégorie)
        if item.parent():
            script_name = item.text(0)
            print(f"Script sélectionné : {script_name}")

            # Vérifier si l’onglet existe déjà
            for i in range(self.tabWidget.count()):
                if self.tabWidget.tabText(i) == script_name:
                    self.tabWidget.setCurrentIndex(i)
                    return

            # Créer un nouvel onglet
            new_tab = QWidget()
            layout = QVBoxLayout()
            editor = QTextEdit()
            editor.setPlainText(f"Contenu du script {script_name}")  # ici tu peux charger le fichier réel
            layout.addWidget(editor)
            new_tab.setLayout(layout)

            self.tabWidget.addTab(new_tab, script_name)
            self.tabWidget.setCurrentWidget(new_tab)

    def close_tab(self, index):
        """Supprime l’onglet à l’index donné."""
        self.tabWidget.removeTab(index)

    # Optionnel : exécution des scripts depuis fichiers
    def run_script(self, file_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("module.name", file_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
