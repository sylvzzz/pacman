# PyInstaller spec: `make package` builds dist/pac-man/.
a = Analysis(
    ["pac-man.py"],
    datas=[("instructions.txt", "."), ("config.json", ".")],
    hiddenimports=["mazegenerator"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="pac-man",
          console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="pac-man")
