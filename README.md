<div align="center">

  <img src="data/media/icon_256.png" alt="App Icon" width="128" />

  <h1>
    SSH Config Studio
  </h1>

  <img src="https://img.shields.io/badge/GTK-4.0-4A90E2?style=for-the-badge&logo=gtk&logoColor=white" alt="GTK" />
  <img src="https://img.shields.io/badge/License-GPL%20v3-00D4AA?style=for-the-badge&logo=gnu&logoColor=white" alt="License" />
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />

  <p>A native <strong>GTK4 desktop app</strong> for editing and validating your <code>~/.ssh/config</code>.</p>
  <p>Search, edit, and validate SSH hosts with a clean UI — no need to touch terminal editors.</p>

</div>

### Preview

<div align="center">
  <img src="data/media/ss1.png" alt="Main Interface" width="45%" style="margin-right: 2%;" />
  <img src="data/media/ss2.png" alt="Preferences Dialog" width="45%" />
</div>

### Features

- **Visual host editor**: Edit common fields (Host, HostName, User, Port, IdentityFile, ForwardAgent, etc.).
- **Inline validation**: Field-level errors are shown directly under inputs; parser checks for duplicate aliases and invalid ports.
- **Search and filter**: Quickly find hosts across aliases, hostnames, users, and identities.
- **Raw/Diff view**: Edit raw `ssh_config` text with instant diff highlighting.
- **Quick actions**: Copy SSH command, test connection, and revert changes.
- **SSH Key Management**: Easily import, generate and use your Public/Private keys.
- **Safe saves**: Automatic backups (configurable), atomic writes, and include support.
- **Keyboard- and mouse-friendly**: Smooth GTK 4 UI, dark theme preference.



## Install

### Build from source
You can clone and run from GNOME Builder.

### Build (Flatpak)

If you prefer Flatpak, use the manifest to build the project.

```bash
flatpak-builder --user --force-clean --install-deps-from=flathub build-dir com.sshconfigstudio.app.json --install

# Run
flatpak run com.sshconfigstudio.app
```

### Usage

1. The app loads `~/.ssh/config` by default. Use the menu → Preferences to choose a different config file or backup directory.
2. Click “+” to add a new host or select a host to edit.
3. Use the Raw/Diff tab for low-level edits; changes are highlighted before saving.
4. Click Save to write changes. A backup can be created automatically (configurable).

### Project structure (high-level)

- `src/ssh_config_parser.py`: Parse/validate/generate SSH config safely.
- `src/ui/`: Adw widgets (`MainWindow`, `HostList`, `HostEditor`, `SearchBar`, `PreferencesDialog`, `TestConnectionDialog`, `SSH Key Manager`).
- `data/ui/*.ui`: GTK Builder UI blueprints.
- `data/ssh-config-studio.gresource.xml`: GResource manifest.
- `data/media/`: App icon and screenshots.
- `src/main.py`: Application entry point.
- `meson.build`, `data/meson.build`, `src/meson.build`: Build and install rules.
- `com.sshconfigstudio.app.json`: Flatpak manifest.
- `po/`: Translations.

### Known issues
- When editng config using Raw/Diff, custom options added manualy wont appear on Advanced page.
- Show/Hide Host editor button icon might not load. 

### Support

- Open an issue on GitHub: `https://github.com/BuddySirJava/ssh-config-studio/issues`
- Or reach me on Telegram: `@Buddy_R`

### Contributing

Issues and pull requests are welcome. Please keep code readable and small, focused edits. If you’re touching UI, prefer inline validation over popups and match the existing GTK 4 patterns.

### License

This project is licensed under the [GNU General Public License v3.0](LICENSE).
