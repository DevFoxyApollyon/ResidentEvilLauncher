import sys

if __name__ == "__main__":
    if "--uninstall" in sys.argv:   # "Adicionar ou remover programas" abre o desinstalador pelo próprio launcher
        from installer.installer import run
        run(sys.argv)
    else:
        from rehub.ui.app import main
        main()
