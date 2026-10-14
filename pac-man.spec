# PyInstaller spec: `make package` builds the single file dist/pac-man.
a = Analysis(
    ["pac-man.py"],
    datas=[("instructions.txt", "."), ("config.json", ".")],
    hiddenimports=["mazegenerator"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="pac-man",
          console=True)
