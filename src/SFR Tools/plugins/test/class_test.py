
label = "/Users/joseph/Downloads/LIB_2N7002P/2N7002P/KiCad/2N7002P.kicad_sym"
import re
a = re.search("\\.kicad_(sym|mod)$", label)
print(a, a!=None)