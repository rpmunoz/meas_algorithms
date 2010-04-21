"""Support for image defects"""

import lsst.afw.image.imageLib as afwImage
import lsst.pex.policy as policy
import lsst.meas.algorithms as algorithms

def policyToBadRegionList(policyFile):
    """Given a Policy file describing a CCD's bad pixels, return a vector of BadRegion::Ptr""" 

    badPixelsPolicy = policy.Policy.createPolicy(policyFile)
    badPixels = algorithms.DefectListT()

    if badPixelsPolicy.exists("Defects"):
        d = badPixelsPolicy.getArray("Defects")
        for reg in d:
            x0 = reg.get("x0")
            width = reg.get("width")
            if not width:
                x1 = reg.get("x1")
                width = x1 - x0 - 1
    
            y0 = reg.get("y0")
            if reg.exists("height"):
                height = reg.get("height")
            else:
                y1 = reg.get("y1")
                height = y1 - y0 - 1
    
            bbox = afwImage.BBox(afwImage.PointI(x0, y0), width, height)
            badPixels.push_back(algorithms.Defect(bbox))
    
    del badPixelsPolicy

    return badPixels