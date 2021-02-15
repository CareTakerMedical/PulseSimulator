from finger import Pressure
import time
import numpy as np
from matplotlib import pyplot as plt


pressure=Pressure()

psi=pressure.mmHg2psi(100.0)
mmHg=pressure.psi2mmHg(psi)

print(psi, mmHg)

print(pressure.psi2mmHg(14.456))
print(pressure.psi2mmHg(16.079))
