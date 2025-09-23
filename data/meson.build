blueprint_compiler = find_program('blueprint-compiler', required: true)

blueprint_files = files(
  'ui/host_editor.blp',
  'ui/host_list.blp',
  'ui/main_window.blp',
  'ui/preferences_dialog.blp',
  'ui/test_connection_dialog.blp',
  'ui/ssh_key_manager_dialog.blp',
  'ui/generate_key_dialog.blp',
  'ui/key_picker_dialog.blp',
  'ui/keyboard_shortcuts_dialog.blp',
  'ui/welcome_view.blp',
  'ui/unsaved_changes_dialog.blp',
)

bp_gen = generator(blueprint_compiler,
  output: '@BASENAME@.ui',
  arguments: ['compile', '--output', '@OUTPUT@', '@INPUT@']
)

compiled_ui_files = bp_gen.process(blueprint_files)

compiled_ui_stamp = custom_target(
  'ui_compiled',
  input: compiled_ui_files,
  output: 'ui_compiled.stamp',
  command: ['touch', '@OUTPUT@'],
)

css_copy = configure_file(input: 'ssh-studio.css', output: 'ssh-studio.css', copy: true)
icon_256_copy = configure_file(input: 'media/icon_256.png', output: 'icon_256.png', copy: true)
icon_128_copy = configure_file(input: 'media/icon_128.png', output: 'icon_128.png', copy: true)

gnome.compile_resources('ssh-studio-resources',
  'ssh-studio.gresource.xml',
  source_dir: join_paths(meson.current_build_dir(), 'ui_compiled.stamp.p'),
  dependencies: compiled_ui_stamp,
  gresource_bundle: true,
  install: true,
  install_dir: join_paths(get_option('datadir'), application_id))

install_data('io.github.BuddySirJava.SSH-Studio.metainfo.xml',
  install_dir: join_paths(get_option('datadir'), 'metainfo'))
