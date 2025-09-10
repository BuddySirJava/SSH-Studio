project('ssh-studio', 'c',
  version: '1.2.0',
  license: 'MIT',
  meson_version: '>= 0.60.0',
  default_options: ['warning_level=2',
                    'buildtype=debugoptimized'])


python = import('python')
python_installation = python.find_installation()

gnome = import('gnome')

application_id = 'com.sshstudio.app'

i18n = import('i18n')
subdir('po')

subdir('src')

subdir('data')

install_data(join_paths(meson.current_source_dir(), 'data', 'ssh-studio.desktop'),
             rename: application_id + '.desktop',
             install_dir: join_paths(get_option('datadir'), 'applications'))

install_data(join_paths(meson.current_source_dir(), 'data', 'media', 'icon_256.png'),
             rename: application_id + '.png',
             install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', '256x256', 'apps'))
install_data(join_paths(meson.current_source_dir(), 'data', 'media', 'icon_256.png'),
             rename: application_id + '.png',
             install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', '128x128', 'apps'))

