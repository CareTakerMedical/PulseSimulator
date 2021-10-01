def convert_mpsi_to_mmhg(val):
    """ Value comes back from the sensor in mPSI; use this function to convert to mmHg.
    """
    return ((.001 * val) * 51.715)
