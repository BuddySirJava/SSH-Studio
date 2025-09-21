class SshStudio < Formula
  desc "GTK4 desktop app to edit and validate your ~/.ssh/config"
  homepage "https://github.com/BuddySirJava/SSH-Studio"
  url "https://github.com/BuddySirJava/SSH-Studio/archive/refs/tags/1.2.3.tar.gz"
  sha256 "8fc311467822c8c858400288386b023b9008bb2f5992966b57052ddd197c9cba"
  license "GPL-3.0-or-later"
  head "https://github.com/BuddySirJava/SSH-Studio.git", branch: "master"

  depends_on "meson" => :build
  depends_on "ninja" => :build
  depends_on "pkg-config" => :build

  depends_on "glib"
  depends_on "gtk4"
  depends_on "libadwaita"
  depends_on "pygobject3"
  depends_on "python@3.13"

  resource "blueprint-compiler" do
    url "https://gitlab.gnome.org/GNOME/blueprint-compiler/-/archive/v0.18.0/blueprint-compiler-v0.18.0.tar.gz"
    sha256 "703c7ccd23cb6f77a8fe9c8cae0f91de9274910ca953de77135b6e79dbff1fc3"
  end

  def install
    resource("blueprint-compiler").stage do
      system "meson", "setup", "build", "--prefix=#{libexec}", "--buildtype=release"
      system "meson", "compile", "-C", "build"
      system "meson", "install", "-C", "build"
    end
    ENV.prepend_path "PATH", libexec/"bin"

    ENV["PYTHON"] = Formula["python@3.13"].opt_bin/"python3"

    inreplace "data/ssh-studio.in", "python3", "#{Formula["python@3.13"].opt_bin}/python3"

    system "meson", "setup", "build", *std_meson_args
    system "meson", "compile", "-C", "build"
    system "meson", "install", "-C", "build"

    python_version = Formula["python@3.13"].version.major_minor
    python_site_packages = lib/"python#{python_version}/site-packages"
    python_site_packages.mkpath

    (python_site_packages/"ssh_studio").mkpath
    (python_site_packages/"ssh_studio/ui").mkpath

    cp_r "src/ssh_config_parser.py", python_site_packages/"ssh_studio/"
    cp_r "src/main.py", python_site_packages/"ssh_studio/"
    cp_r "src/__init__.py", python_site_packages/"ssh_studio/"
    cp_r Dir["src/ui/*.py"], python_site_packages/"ssh_studio/ui/"
    cp_r "src/ui/__init__.py", python_site_packages/"ssh_studio/ui/"

    (libexec/"bin").mkpath
    mv bin/"ssh-studio", libexec/"bin/ssh-studio" if (bin/"ssh-studio").exist?
    (bin/"ssh-studio").write <<~SH
      #!/bin/bash
      export PYTHONPATH="#{python_site_packages}"
      exec "#{Formula["python@3.13"].opt_bin}/python3" -m ssh_studio.main "$@"
    SH
    chmod 0755, bin/"ssh-studio"

    app_root = prefix/"Applications/SSH Studio.app/Contents"
    (app_root/"MacOS").mkpath
    (app_root/"Resources").mkpath

    (app_root/"Info.plist").write <<~PLIST
      <?xml version="1.0" encoding="UTF-8"?>
      <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
      <plist version="1.0">
      <dict>
        <key>CFBundleName</key><string>SSH Studio</string>
        <key>CFBundleIdentifier</key><string>io.github.BuddySirJava.SSH-Studio</string>
        <key>CFBundleVersion</key><string>#{version}</string>
        <key>CFBundleShortVersionString</key><string>#{version}</string>
        <key>CFBundleExecutable</key><string>ssh-studio</string>
        <key>CFBundlePackageType</key><string>APPL</string>
        <key>LSMinimumSystemVersion</key><string>11.0</string>
        <key>LSApplicationCategoryType</key><string>public.app-category.developer-tools</string>
      </dict>
      </plist>
    PLIST

    (app_root/"MacOS/ssh-studio").write <<~SH
      #!/bin/bash
      export PYTHONPATH="#{python_site_packages}"
      exec "#{Formula["python@3.13"].opt_bin}/python3" -m ssh_studio.main "$@"
    SH
    chmod 0755, (app_root/"MacOS/ssh-studio")
  end

  def caveats
    <<~EOS
      A minimal app bundle was installed at:
        #{opt_prefix}/Applications/SSH Studio.app

      To add a Desktop shortcut:
        ln -sf "#{opt_prefix}/Applications/SSH Studio.app" "$HOME/Desktop/SSH Studio.app"

      To add it to /Applications (optional):
        ln -sf "#{opt_prefix}/Applications/SSH Studio.app" "/Applications/SSH Studio.app"
    EOS
  end

  test do
    system bin/"ssh-studio", "--help"
  end
end
