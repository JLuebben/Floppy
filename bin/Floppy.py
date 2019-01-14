#!python3
if __name__ == '__main__':
    try:
        import floppy.main
    except ImportError:
        import sys
        sys.path.append("..")
        import floppy.main
    floppy.main.run()
