import sys
from PyQt6 import uic
from PyQt6.QtWidgets import QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("ui/main_window.ui", self)  # Charge le .ui

        # Récupérer le QTreeWidget créé dans Designer
        self.treeScripts = self.findChild(QTreeWidget, "treeScripts")
        if not self.treeScripts:
            raise ValueError("Le QTreeWidget 'treeScripts' n'a pas été trouvé dans le .ui")

        # Remplir le treeScripts avec des catégories et scripts
        self.load_scripts()

    def load_scripts(self):
        # ----------------- Catégorie 1 -----------------
        cat1 = QTreeWidgetItem(self.treeScripts)
        cat1.setText(0, "Catégorie 1")
        cat1.setExpanded(True)

        script_a = QTreeWidgetItem(cat1)
        script_a.setText(0, "Script A")

        script_b = QTreeWidgetItem(cat1)
        script_b.setText(0, "Script B")

        # ----------------- Catégorie 2 -----------------
        cat2 = QTreeWidgetItem(self.treeScripts)
        cat2.setText(0, "Catégorie 2")
        cat2.setExpanded(True)

        script_c = QTreeWidgetItem(cat2)
        script_c.setText(0, "Script C")

        script_d = QTreeWidgetItem(cat2)
        script_d.setText(0, "Script D")

        # ----------------- Catégorie 3 -----------------
        cat3 = QTreeWidgetItem(self.treeScripts)
        cat3.setText(0, "Catégorie 3")
        cat3.setExpanded(True)

        script_e = QTreeWidgetItem(cat3)
        script_e.setText(0, "Script E")

        script_f = QTreeWidgetItem(cat3)
        script_f.setText(0, "Script F")

        # Connecte le clic sur un script
        self.treeScripts.itemClicked.connect(self.on_item_clicked)

    def on_item_clicked(self, item, column):
        # Si c’est un script (pas une catégorie)
        if item.parent():
            print(f"Script sélectionné : {item.text(0)}")
            # Ici tu peux remplacer print par l’exécution réelle du script
            # self.run_script(file_path)

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
