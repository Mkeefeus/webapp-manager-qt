#!/usr/bin/python3

#   1. Standard library imports.
import gettext
import locale
import os
import shutil
import subprocess
import sys

#   2. Related third party imports.
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTreeWidget, QTreeWidgetItem, QPushButton, QLineEdit, QLabel,
    QComboBox, QMessageBox, QStackedWidget, QScrollArea,
    QCheckBox, QDialog, QDialogButtonBox, QMenuBar
)
from PySide6.QtCore import Qt, QThread, Signal, QSize, QTranslator, QLibraryInfo
from PySide6.QtGui import QIcon, QPixmap, QAction, QKeySequence
import setproctitle

try:
    import tldextract
    TLDEXTRACT_AVAILABLE = True
except ImportError:
    TLDEXTRACT_AVAILABLE = False

try:
    from PyKDE5.kdeui import KIconDialog
    KDE_AVAILABLE = True
except ImportError:
    KDE_AVAILABLE = False

#   3. Local application/library specific imports.
from common import (
    WebAppManager, download_favicon, ICONS_DIR,
    BROWSER_TYPE_FIREFOX, BROWSER_TYPE_FIREFOX_FLATPAK,
    BROWSER_TYPE_ZEN_FLATPAK, BROWSER_TYPE_FIREFOX_SNAP
)

setproctitle.setproctitle("webapp-manager")

# i18n
APP = 'webapp-manager'
LOCALE_DIR = "/usr/share/locale"
locale.bindtextdomain(APP, LOCALE_DIR)
gettext.bindtextdomain(APP, LOCALE_DIR)
gettext.textdomain(APP)
_ = gettext.gettext


class FaviconDownloadThread(QThread):
    """Thread for downloading favicons asynchronously"""
    finished = Signal(list)  # Emits list of (origin, pil_image, path) tuples
    
    def __init__(self, url):
        super().__init__()
        self.url = url
    
    def run(self):
        images = download_favicon(self.url)
        self.finished.emit(images)


class KIconButton(QPushButton):
    """Custom icon button that opens KIconDialog or fallback icon selector"""
    icon_changed = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_icon = "webapp-manager"
        self.setIconSize(QSize(48, 48))
        self.setFixedSize(64, 64)
        self.update_icon()
        self.clicked.connect(self.choose_icon)
    
    def update_icon(self):
        icon = QIcon.fromTheme(self.current_icon)
        if icon.isNull():
            # Try loading from file path
            if os.path.exists(self.current_icon):
                icon = QIcon(self.current_icon)
        self.setIcon(icon)
    
    def choose_icon(self):
        if KDE_AVAILABLE:
            # Use KDE's native icon chooser
            dialog = KIconDialog()
            icon_name = dialog.getIcon()
            if icon_name:
                self.set_icon(icon_name)
        else:
            # Fallback: Simple file chooser
            from PySide6.QtWidgets import QFileDialog
            filename, _ = QFileDialog.getOpenFileName(
                self, _("Choose Icon"), "", 
                "Images (*.png *.jpg *.svg);;All Files (*)"
            )
            if filename:
                self.set_icon(filename)
    
    def set_icon(self, icon_name):
        self.current_icon = icon_name
        self.update_icon()
        self.icon_changed.emit(icon_name)
    
    def get_icon(self):
        return self.current_icon


class WebAppManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.manager = WebAppManager()
        self.selected_webapp = None
        self.edit_mode = False
        self.favicon_thread = None
        
        self.setWindowTitle(_("Web Apps"))
        self.setWindowIcon(QIcon.fromTheme("webapp-manager"))
        self.resize(900, 600)
        
        self.setup_ui()
        self.setup_menus()
        self.load_webapps()
    
    def setup_ui(self):
        """Create the main UI"""
        # Central widget with stacked layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Stacked widget for different pages
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)
        
        # Create pages
        self.main_page = self.create_main_page()
        self.add_page = self.create_add_page()
        self.favicon_page = self.create_favicon_page()
        
        self.stack.addWidget(self.main_page)
        self.stack.addWidget(self.add_page)
        self.stack.addWidget(self.favicon_page)
        
        self.stack.setCurrentWidget(self.main_page)
    
    def create_main_page(self):
        """Create the main page with webapp list"""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Toolbar
        toolbar = QHBoxLayout()
        self.add_button = QPushButton(_("Add"))
        self.add_button.setIcon(QIcon.fromTheme("list-add"))
        self.add_button.clicked.connect(self.on_add_button)
        
        self.edit_button = QPushButton(_("Edit"))
        self.edit_button.setIcon(QIcon.fromTheme("document-edit"))
        self.edit_button.setEnabled(False)
        self.edit_button.clicked.connect(self.on_edit_button)
        
        self.remove_button = QPushButton(_("Remove"))
        self.remove_button.setIcon(QIcon.fromTheme("list-remove"))
        self.remove_button.setEnabled(False)
        self.remove_button.clicked.connect(self.on_remove_button)
        
        self.run_button = QPushButton(_("Launch"))
        self.run_button.setIcon(QIcon.fromTheme("system-run"))
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self.on_run_button)
        
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.edit_button)
        toolbar.addWidget(self.remove_button)
        toolbar.addWidget(self.run_button)
        toolbar.addStretch()
        
        layout.addLayout(toolbar)
        
        # TreeWidget for webapps
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels([_("Icon"), _("Name"), _("Browser")])
        self.tree_widget.setColumnWidth(0, 50)
        self.tree_widget.setColumnWidth(1, 300)
        self.tree_widget.setIconSize(QSize(32, 32))
        self.tree_widget.setSelectionMode(QTreeWidget.SingleSelection)
        self.tree_widget.itemSelectionChanged.connect(self.on_webapp_selected)
        self.tree_widget.itemDoubleClicked.connect(self.on_webapp_activated)
        
        # Sort by name
        self.tree_widget.setSortingEnabled(True)
        self.tree_widget.sortByColumn(1, Qt.AscendingOrder)
        
        layout.addWidget(self.tree_widget)
        
        return page
    
    def create_add_page(self):
        """Create the add/edit page"""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Form layout
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        
        # Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel(_("Name:")))
        self.name_entry = QLineEdit()
        self.name_entry.textChanged.connect(self.on_name_entry_changed)
        name_layout.addWidget(self.name_entry)
        form_layout.addLayout(name_layout)
        self.name_entry.setPlaceholderText(_("Website name"))
        
        # Description
        desc_layout = QHBoxLayout()
        desc_layout.addWidget(QLabel(_("Description:")))
        self.desc_entry = QLineEdit()
        desc_layout.addWidget(self.desc_entry)
        form_layout.addLayout(desc_layout)
        self.desc_entry.setPlaceholderText(_("Web App"))
        
        # URL
        url_layout = QHBoxLayout()
        self.url_label = QLabel(_("Address:"))
        url_layout.addWidget(self.url_label)
        self.url_entry = QLineEdit()
        self.url_entry.textChanged.connect(self.on_url_entry_changed)
        url_layout.addWidget(self.url_entry)
        self.favicon_button = QPushButton(_("Find icons online"))
        self.favicon_button.setEnabled(False)
        self.favicon_button.clicked.connect(self.on_favicon_button)
        url_layout.addWidget(self.favicon_button)
        form_layout.addLayout(url_layout)
        self.url_entry.setPlaceholderText(_("https://www.website.com"))
        
        # Icon
        icon_layout = QHBoxLayout()
        icon_layout.addWidget(QLabel(_("Icon:")))
        self.icon_button = KIconButton()
        self.icon_button.icon_changed.connect(self.on_icon_changed)
        icon_layout.addWidget(self.icon_button)
        icon_layout.addStretch()
        form_layout.addLayout(icon_layout)
        
        # Category
        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel(_("Category:")))
        self.category_combo = QComboBox()
        categories = [
            ("WebApps", _("Web")),
            ("Network", _("Internet")),
            ("Utility", _("Accessories")),
            ("Game", _("Games")),
            ("Graphics", _("Graphics")),
            ("Office", _("Office")),
            ("AudioVideo", _("Sound & Video")),
            ("Development", _("Programming")),
            ("Education", _("Education"))
        ]
        for cat_id, cat_name in categories:
            self.category_combo.addItem(cat_name, cat_id)
        category_layout.addWidget(self.category_combo)
        form_layout.addLayout(category_layout)
        
        # Browser
        browser_layout = QHBoxLayout()
        self.browser_label = QLabel(_("Browser:"))
        browser_layout.addWidget(self.browser_label)
        self.browser_combo = QComboBox()
        self.populate_browsers()
        self.browser_combo.currentIndexChanged.connect(self.on_browser_changed)
        browser_layout.addWidget(self.browser_combo)
        form_layout.addLayout(browser_layout)
        
        # Custom Parameters
        custom_layout = QHBoxLayout()
        custom_layout.addWidget(QLabel(_("Custom parameters:")))
        self.custom_parameters_entry = QLineEdit()
        custom_layout.addWidget(self.custom_parameters_entry)
        form_layout.addLayout(custom_layout)
        self.custom_parameters_entry.setPlaceholderText(_("Custom browser parameters"))
        
        # Switches/Checkboxes
        self.isolated_checkbox = QCheckBox(_("Isolated profile:"))
        self.isolated_checkbox.setChecked(True)
        form_layout.addWidget(self.isolated_checkbox)
        self.isolated_checkbox.setToolTip(_("If this option is enabled the website will run with its own browser profile."))
        
        self.navbar_checkbox = QCheckBox(_("Navigation bar:"))
        form_layout.addWidget(self.navbar_checkbox)
        
        self.private_checkbox = QCheckBox(_("Private/Incognito Window:"))
        form_layout.addWidget(self.private_checkbox)
        
        form_layout.addStretch()
        layout.addWidget(form_widget)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_button = QPushButton(_("Cancel"))
        cancel_button.clicked.connect(self.on_cancel_button)
        button_layout.addWidget(cancel_button)
        
        self.ok_button = QPushButton(_("OK"))
        self.ok_button.setEnabled(False)
        self.ok_button.clicked.connect(self.on_ok_button)
        button_layout.addWidget(self.ok_button)
        
        layout.addLayout(button_layout)
        
        return page
    
    def create_favicon_page(self):
        """Create the favicon selection page"""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        layout.addWidget(QLabel(_("Choose an icon")))
        
        # Scroll area for favicon grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.favicon_container = QWidget()
        self.favicon_layout = QVBoxLayout(self.favicon_container)
        
        scroll.setWidget(self.favicon_container)
        layout.addWidget(scroll)
        
        # Cancel button
        cancel_button = QPushButton(_("Cancel"))
        cancel_button.clicked.connect(self.on_cancel_favicon_button)
        layout.addWidget(cancel_button)
        
        return page
    
    def populate_browsers(self):
        """Populate browser combo box"""
        num_browsers = 0
        for browser in self.manager.get_supported_browsers():
            if os.path.exists(browser.test_path):
                self.browser_combo.addItem(browser.name, browser)
                num_browsers += 1
        
        if num_browsers == 0:
            self.add_button.setEnabled(False)
            self.add_button.setToolTip(_("No supported browsers were detected."))
        
        if num_browsers < 2:
            self.browser_label.hide()
            self.browser_combo.hide()
    
    def setup_menus(self):
        """Setup application menu"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu(_("&File"))
        
        quit_action = QAction(_("Quit"), self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        
        # Help menu
        help_menu = menubar.addMenu(_("Help"))
        
        shortcuts_action = QAction(_("Keyboard Shortcuts"), self)
        shortcuts_action.setShortcut(QKeySequence("Ctrl+K"))
        shortcuts_action.triggered.connect(self.show_shortcuts)
        help_menu.addAction(shortcuts_action)
        
        about_action = QAction(_("About"), self)
        about_action.setShortcut(QKeySequence("F1"))
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def load_webapps(self):
        """Load all webapps into the tree"""
        self.tree_widget.clear()
        self.selected_webapp = None
        self.edit_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        self.run_button.setEnabled(False)
        
        webapps = self.manager.get_webapps()
        for webapp in webapps:
            if webapp.is_valid:
                item = QTreeWidgetItem()
                
                # Icon
                if "/" in webapp.icon and os.path.exists(webapp.icon):
                    pixmap = QPixmap(webapp.icon).scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    item.setIcon(0, QIcon(pixmap))
                else:
                    icon = QIcon.fromTheme(webapp.icon)
                    if icon.isNull():
                        icon = QIcon.fromTheme("webapp-manager")
                    item.setIcon(0, icon)
                
                item.setText(1, webapp.name)
                item.setText(2, webapp.web_browser or "")
                item.setData(0, Qt.UserRole, webapp)
                
                self.tree_widget.addTopLevelItem(item)
        
        # Select first item
        if self.tree_widget.topLevelItemCount() > 0:
            self.tree_widget.setCurrentItem(self.tree_widget.topLevelItem(0))
        
        self.stack.setCurrentWidget(self.main_page)
    
    def on_webapp_selected(self):
        """Handle webapp selection"""
        items = self.tree_widget.selectedItems()
        if items:
            self.selected_webapp = items[0].data(0, Qt.UserRole)
            self.edit_button.setEnabled(True)
            self.remove_button.setEnabled(True)
            self.run_button.setEnabled(True)
        else:
            self.selected_webapp = None
            self.edit_button.setEnabled(False)
            self.remove_button.setEnabled(False)
            self.run_button.setEnabled(False)
    
    def on_webapp_activated(self, item, column):
        """Handle double-click on webapp"""
        webapp = item.data(0, Qt.UserRole)
        if webapp:
            self.run_webapp(webapp)
    
    def on_add_button(self):
        """Show add webapp page"""
        self.name_entry.clear()
        self.desc_entry.clear()
        self.url_entry.clear()
        self.custom_parameters_entry.clear()
        self.icon_button.set_icon("webapp-manager")
        self.category_combo.setCurrentIndex(0)
        self.browser_combo.setCurrentIndex(0)
        self.isolated_checkbox.setChecked(True)
        self.navbar_checkbox.setChecked(False)
        self.private_checkbox.setChecked(False)
        
        self.browser_label.show()
        self.browser_combo.show()
        self.show_hide_browser_widgets()
        
        self.edit_mode = False
        self.stack.setCurrentWidget(self.add_page)
        self.name_entry.setFocus()
    
    def on_edit_button(self):
        """Show edit webapp page"""
        if not self.selected_webapp:
            return
        
        self.name_entry.setText(self.selected_webapp.name)
        self.desc_entry.setText(self.selected_webapp.desc)
        self.url_entry.setText(self.selected_webapp.url)
        self.custom_parameters_entry.setText(self.selected_webapp.custom_parameters)
        self.icon_button.set_icon(self.selected_webapp.icon)
        self.navbar_checkbox.setChecked(self.selected_webapp.navbar)
        self.isolated_checkbox.setChecked(self.selected_webapp.isolate_profile)
        self.private_checkbox.setChecked(self.selected_webapp.privatewindow)
        
        # Set browser
        for i in range(self.browser_combo.count()):
            browser = self.browser_combo.itemData(i)
            if browser.name == self.selected_webapp.web_browser:
                self.browser_combo.setCurrentIndex(i)
                break
        
        # Set category
        for i in range(self.category_combo.count()):
            if self.category_combo.itemData(i) == self.selected_webapp.category:
                self.category_combo.setCurrentIndex(i)
                break
        
        self.browser_label.hide()
        self.browser_combo.hide()
        self.show_hide_browser_widgets()
        
        self.edit_mode = True
        self.stack.setCurrentWidget(self.add_page)
        self.name_entry.setFocus()
    
    def on_remove_button(self):
        """Remove selected webapp"""
        if not self.selected_webapp:
            return
        
        reply = QMessageBox.question(
            self,
            _("Delete '%s'") % self.selected_webapp.name,
            (_("Are you sure you want to delete '%s'?") % self.selected_webapp.name) + "\n\n" + _("This Web App will be permanently lost."),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.manager.delete_webbapp(self.selected_webapp)
            self.load_webapps()
    
    def on_run_button(self):
        """Run selected webapp"""
        if self.selected_webapp:
            self.run_webapp(self.selected_webapp)
    
    def run_webapp(self, webapp):
        """Execute a webapp"""
        if webapp:
            print(f"Running {webapp.path}")
            print(f"Executing {webapp.exec}")
            subprocess.Popen(webapp.exec, shell=True)
    
    def on_ok_button(self):
        """Save webapp"""
        category = self.category_combo.currentData()
        browser = self.browser_combo.currentData()
        name = self.name_entry.text()
        desc = self.desc_entry.text().strip()
        url = self.get_url()
        isolate_profile = self.isolated_checkbox.isChecked()
        navbar = self.navbar_checkbox.isChecked()
        privatewindow = self.private_checkbox.isChecked()
        icon = self.icon_button.get_icon()
        custom_parameters = self.custom_parameters_entry.text()
        
        if "/tmp" in icon:
            # Move icon to permanent location
            filename = "".join(filter(str.isalpha, name)) + ".png"
            new_path = os.path.join(ICONS_DIR, filename)
            shutil.copyfile(icon, new_path)
            icon = new_path
        
        if self.edit_mode:
            self.manager.edit_webapp(
                self.selected_webapp.path, name, desc, browser, url, icon,
                category, custom_parameters, self.selected_webapp.codename,
                isolate_profile, navbar, privatewindow
            )
        else:
            self.manager.create_webapp(
                name, desc, url, icon, category, browser, custom_parameters,
                isolate_profile, navbar, privatewindow
            )
        
        self.load_webapps()
    
    def on_cancel_button(self):
        """Cancel add/edit"""
        self.load_webapps()
    
    def on_cancel_favicon_button(self):
        """Cancel favicon selection"""
        self.stack.setCurrentWidget(self.add_page)
    
    def on_favicon_button(self):
        """Download favicons"""
        url = self.get_url()
        if not url:
            return
        
        self.favicon_button.setEnabled(False)
        self.favicon_thread = FaviconDownloadThread(url)
        self.favicon_thread.finished.connect(self.show_favicons)
        self.favicon_thread.start()
    
    def show_favicons(self, images):
        """Display downloaded favicons"""
        self.favicon_button.setEnabled(True)
        
        if not images:
            QMessageBox.information(self, _("No Icons Found"), _("No icons were found for this website."))
            return
        
        # Clear previous icons
        while self.favicon_layout.count():
            child = self.favicon_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Create a grid layout for icons
        grid = QGridLayout()
        row = 0
        col = 0
        max_cols = 4  # 4 icons per row
        
        for origin, pil_image, path in images:
            button = QPushButton()
            pixmap = QPixmap(path).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            button.setIcon(QIcon(pixmap))
            button.setIconSize(QSize(64, 64))
            button.setFixedSize(80, 80)
            button.setToolTip(f"{origin}\n{pil_image.width}x{pil_image.height}")
            button.clicked.connect(lambda checked, p=path: self.on_favicon_selected(p))
            
            grid.addWidget(button, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        self.favicon_layout.addLayout(grid)
        self.favicon_layout.addStretch()
        
        self.stack.setCurrentWidget(self.favicon_page)
    
    def on_favicon_selected(self, path):
        """Handle favicon selection"""
        self.icon_button.set_icon(path)
        self.stack.setCurrentWidget(self.add_page)
    
    def on_browser_changed(self):
        """Handle browser selection change"""
        self.show_hide_browser_widgets()
    
    def show_hide_browser_widgets(self):
        """Show/hide widgets based on browser type"""
        browser = self.browser_combo.currentData()
        if not browser:
            return
        
        is_firefox = browser.browser_type in [
            BROWSER_TYPE_FIREFOX, BROWSER_TYPE_FIREFOX_FLATPAK,
            BROWSER_TYPE_FIREFOX_SNAP, BROWSER_TYPE_ZEN_FLATPAK
        ]
        
        self.isolated_checkbox.setVisible(not is_firefox)
        self.navbar_checkbox.setVisible(is_firefox)
        self.private_checkbox.setVisible(True)
    
    def on_name_entry_changed(self):
        """Handle name entry change"""
        self.toggle_ok_sensitivity()
    
    def on_url_entry_changed(self):
        """Handle URL entry change"""
        url = self.get_url()
        self.favicon_button.setEnabled(bool(url))
        self.toggle_ok_sensitivity()
        self.guess_icon()
    
    def on_icon_changed(self, icon):
        """Handle icon change"""
        pass  # Nothing needed here currently
    
    def toggle_ok_sensitivity(self):
        """Enable/disable OK button based on form validity"""
        valid = bool(self.name_entry.text() and self.get_url())
        self.ok_button.setEnabled(valid)
    
    def get_url(self):
        """Get validated URL from entry"""
        url = self.url_entry.text().strip()
        if not url:
            return ""
        if "://" not in url:
            url = f"http://{url}"
        return url
    
    def guess_icon(self):
        """Try to guess icon from URL"""
        url = self.get_url().lower()
        if not url:
            return
        
        info = tldextract.extract(url)
        if not info.domain:
            return
        
        icon = None
        if info.domain == "google" and info.subdomain:
            if info.subdomain == "mail":
                icon = "web-google-gmail"
            else:
                icon = f"web-{info.domain}-{info.subdomain}"
        elif info.domain == "gmail":
            icon = "web-google-gmail"
        elif info.domain == "youtube":
            icon = "web-google-youtube"
        
        if icon and not QIcon.fromTheme(icon).isNull():
            self.icon_button.set_icon(icon)
        elif not QIcon.fromTheme(f"web-{info.domain}").isNull():
            self.icon_button.set_icon(f"web-{info.domain}")
        elif not QIcon.fromTheme(info.domain).isNull():
            self.icon_button.set_icon(info.domain)
    
    def show_shortcuts(self):
        """Show keyboard shortcuts dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle(_("Shortcuts"))
        layout = QVBoxLayout(dialog)
        
        # Web Apps category
        webapps_label = QLabel(f"<h3>{_('Web Apps')}</h3>")
        layout.addWidget(webapps_label)
        
        webapp_shortcuts = [
            (_("Add"), "Ctrl+N"),
            (_("Edit"), "Ctrl+E"),
            (_("Remove"), "Ctrl+D"),
            (_("Launch"), "Space / Enter"),
        ]
        
        for action, shortcut in webapp_shortcuts:
            label = QLabel(f"<b>{action}:</b> {shortcut}")
            layout.addWidget(label)
        
        # Add spacing between categories
        layout.addSpacing(20)
        
        # Other Shortcuts category
        other_label = QLabel(f"<h3>{_('Other Shortcuts')}</h3>")
        layout.addWidget(other_label)
        
        other_shortcuts = [
            (_("Go Back"), "Escape"),
            (_("About"), "F1"),
            (_("Shortcuts"), "Ctrl+K"),
            (_("Quit"), "Ctrl+Q"),
        ]
        
        for action, shortcut in other_shortcuts:
            label = QLabel(f"<b>{action}:</b> {shortcut}")
            layout.addWidget(label)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        
        dialog.exec()
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            _("About"),
            _("Web Apps") + "\n\n" + _("Run websites as if they were apps") + "\n\nVersion: @VERSION@"
        )
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if event.modifiers() == Qt.ControlModifier:
            if event.key() == Qt.Key_N and self.stack.currentWidget() == self.main_page:
                self.on_add_button()
            elif event.key() == Qt.Key_E and self.stack.currentWidget() == self.main_page:
                self.on_edit_button()
            elif event.key() == Qt.Key_D and self.stack.currentWidget() == self.main_page:
                self.on_remove_button()
            elif event.key() in (Qt.Key_Q, Qt.Key_W):
                self.close()
        elif event.key() == Qt.Key_Escape:
            if self.stack.currentWidget() != self.main_page:
                self.load_webapps()
        
        super().keyPressEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("webapp-manager")
    app.setOrganizationName("webapp-manager")
    app.setWindowIcon(QIcon.fromTheme("webapp-manager"))
    
    # Load Qt's built-in translations for dialog buttons, etc.
    qt_translator = QTranslator()
    # Get the current locale from environment or system
    current_locale = locale.getlocale()[0]
    if current_locale:
        # Extract language code (e.g., 'es_ES' -> 'es')
        lang_code = current_locale.split('_')[0]
        
        # Try to load Qt translations from system location
        translations_path = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
        if qt_translator.load(f"qtbase_{lang_code}", translations_path):
            app.installTranslator(qt_translator)
    
    window = WebAppManagerWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()