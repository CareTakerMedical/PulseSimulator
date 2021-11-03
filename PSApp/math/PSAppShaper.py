import numpy as np
from struct import unpack
from math import floor, ceil
from statistics import mean
from copy import deepcopy

def shape_pulse(pts):
    lpts = len(pts)

    # Create two 'zeros' arrays
    si = [0] * lpts
    nsi = [0] * lpts

    # Mean removal
    avg = floor(mean(pts))

    # Integrate
    for i in range(1,lpts):
        nsi[i] = nsi[(i - 1)] + (pts[(i - 1)] - avg)

    # Perform slope corrections
    midpt = ceil(lpts/2.0)
    for j in range(2):
        fmin = min(nsi[1:20])
        findex = nsi[1:20].index(fmin)
        findex += 1
        bmin = min(nsi[midpt:lpts])
        bindex = nsi[midpt:lpts].index(bmin)
        bindex += midpt
        slope = (bmin - fmin) / (bindex - findex)
        for i in range(lpts):
            si[i] = nsi[i] - floor(i * slope) - nsi[findex]
        nsi = deepcopy(si)

    # Marry up the point where the integrated pulse starts to tail downward with the first point of the
    # pulse.  Start at the back, where the integral is linear, and try to figure out where the slope
    # begins to flatten out.
    threshold = 500
    rsi = deepcopy(nsi)
    end = 0
    i = len(rsi) - 1
    while (i > 0):
        if ((rsi[(i - 1)] - rsi[i]) < threshold):
            end = i
            break
        i -= 1

    # Calculate the new slope
    new_slope = (rsi[end] - rsi[0]) / (256 - end)

    # Adjust the points
    for i in range((end + 1),len(rsi)):
        rsi[i] = rsi[(i - 1)] - new_slope

    # Now remove any offset and re-scale all of the points so that the minimum is at 0 and the maximum
    # is at 8192 (13b)
    rmin = min(rsi)
    rindex = rsi.index(rmin)
    for i in range(len(rsi)):
        rsi[i] -= rsi[rindex]
    rmax = max(rsi)
    rscale = 8192.0 / rmax
    for i in range(len(rsi)):
        rsi[i] = round(rscale * rsi[i])

    return rsi
