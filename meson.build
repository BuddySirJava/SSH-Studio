project('ssh-studio', 'c',
  version: '1.3.1',
  license: 'GPL-3.0-or-later',
  meson_version: '>= 0.60.0',
  default_options: [
    'warning_level=2',
    'buildtype=debugoptimized',
    'python.install_env=auto',
    'python.platlibdir='
  ])

python = import('python')
python_installation = python.find_installation('python3', required: true)

gnome = import('gnome')

gtksource_dep = dependency('gtksourceview-5', version: '>= 5.0.0')

application_id = 'io.github.BuddySirJava.SSH-Studio'

i18n = import('i18n')
subdir('po')

subdir('src')

subdir('data')

if get_option('install_desktop_file')
  install_data(
    join_paths(meson.current_source_dir(), 'data', application_id + '.desktop'),
    install_dir: join_paths(get_option('datadir'), 'applications')
  )
endif

install_data(
  join_paths(meson.current_source_dir(), 'data', 'ssh-studio.in'),
  rename: 'ssh-studio',
  install_mode: 'rwxr-xr-x',
  install_dir: join_paths(get_option('bindir'))
)

if get_option('install_icons')
  icon_sizes = ['128', '256', '512']
  icon_extensions = ['png', 'png', 'png']

  foreach i : range(icon_sizes.length())
    size = icon_sizes[i]
    ext = icon_extensions[i]
    install_data(
      join_paths(meson.current_source_dir(), 'data', 'media', 'icon_' + size + '.' + ext),
      rename: application_id + '.' + ext,
      install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', size + 'x' + size, 'apps')
    )
  endforeach

  install_data(
    join_paths(meson.current_source_dir(), 'data', 'media', 'icon.svg'),
    rename: application_id + '.svg',
    install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', 'scalable', 'apps')
  )
endif

if get_option('install_metainfo')
  install_data(
    join_paths(meson.current_source_dir(), 'data', application_id + '.metainfo.xml'),
    install_dir: join_paths(get_option('datadir'), 'metainfo')
  )
endif

