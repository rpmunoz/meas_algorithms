# 
# LSST Data Management System
# Copyright 2008, 2009, 2010, 2011 LSST Corporation.
# 
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the LSST License Statement and 
# the GNU General Public License along with this program.  If not, 
# see <http://www.lsstcorp.org/LegalNotices/>.
#
import math
import lsst.pex.config as pexConfig
import lsst.pex.exceptions as pexExceptions
import lsst.afw.table as afwTable
import lsst.pipe.base as pipeBase
import lsst.afw.display.ds9 as ds9

from . import algorithmsLib
from .algorithmRegistry import *
from .replaceWithNoise import *

__all__ = "SourceSlotConfig", "SourceMeasurementConfig", "SourceMeasurementTask"

class SourceSlotConfig(pexConfig.Config):

    centroid = pexConfig.Field(dtype=str, default="centroid.sdss", optional=True,
                             doc="the name of the centroiding algorithm used to set source x,y")
    shape = pexConfig.Field(dtype=str, default="shape.sdss", optional=True,
                          doc="the name of the algorithm used to set source moments parameters")
    apFlux = pexConfig.Field(dtype=str, default="flux.sinc", optional=True,
                           doc="the name of the algorithm used to set the source aperture flux slot")
    modelFlux = pexConfig.Field(dtype=str, default="flux.gaussian", optional=True,
                           doc="the name of the algorithm used to set the source model flux slot")
    psfFlux = pexConfig.Field(dtype=str, default="flux.psf", optional=True,
                            doc="the name of the algorithm used to set the source psf flux slot")
    instFlux = pexConfig.Field(dtype=str, default="flux.gaussian", optional=True,
                             doc="the name of the algorithm used to set the source inst flux slot")

    def setupTable(self, table, prefix=None):
        """Convenience method to setup a table's slots according to the config definition.

        This is defined in the Config class to support use in unit tests without needing
        to construct a Task object.
        """
        if prefix is None: prefix = ""
        if self.centroid is not None: table.defineCentroid(prefix + self.centroid)
        if self.shape is not None: table.defineShape(prefix + self.shape)
        if self.apFlux is not None: table.defineApFlux(prefix + self.apFlux)
        if self.modelFlux is not None: table.defineModelFlux(prefix + self.modelFlux)
        if self.psfFlux is not None: table.definePsfFlux(prefix + self.psfFlux)
        if self.instFlux is not None: table.defineInstFlux(prefix + self.instFlux)
    
class SourceMeasurementConfig(pexConfig.Config):
    """
    Configuration for SourceMeasurementTask.
    A configured instance of MeasureSources can be created using the
    makeMeasureSources method.
    """

    slots = pexConfig.ConfigField(
        dtype = SourceSlotConfig,
        doc="Mapping from algorithms to special aliases in Source.\n"
        )

    algorithms = AlgorithmRegistry.all.makeField(
        multi=True,
        default=["flags.pixel",
                 "centroid.gaussian", "centroid.naive",
                 "shape.sdss",
                 "flux.gaussian", "flux.naive", "flux.psf", "flux.sinc",
                 "correctfluxes",
                 "classification.extendedness",
                 "skycoord",
                 ],
        doc="Algorithms that will be run by default."
        )
    
    centroider = AlgorithmRegistry.filter(CentroidConfig).makeField(
        multi=False, default="centroid.sdss", optional=True,
        doc="Configuration for the initial centroid algorithm used to\n"\
            "feed center points to other algorithms.\n\n"\
            "Note that this is in addition to the centroider listed in\n"\
            "the 'algorithms' field; the same name should not appear in\n"\
            "both.\n\n"\
            "This field DOES NOT set which field name will be used to define\n"\
            "the alias for source.getX(), source.getY(), etc.\n"
        )

    doReplaceWithNoise = pexConfig.Field(dtype=bool, default=True, optional=False,
                                         doc='When measuring, replace other detected footprints with noise?')

    replaceWithNoise = pexConfig.ConfigurableField(
        target = ReplaceWithNoiseTask,
        doc = ("Task for replacing other sources by noise when measuring sources; run when " +
               "'doReplaceWithNoise' is set."),
    )

    prefix = pexConfig.Field(dtype=str, optional=True, default=None, doc="prefix for all measurement fields")

    def validate(self):
        pexConfig.Config.validate(self)
        if self.centroider.name in self.algorithms.names:
            raise ValueError("The algorithm in the 'centroider' field must not also appear in the "\
                                 "'algorithms' field.")
        if self.slots.centroid is not None and (self.slots.centroid not in self.algorithms.names
                                                and self.slots.centroid != self.centroider.name):
            raise ValueError("source centroid slot algorithm '%s' is not being run." % self.slots.astrom)
        if self.slots.shape is not None and self.slots.shape not in self.algorithms.names:
            raise ValueError("source shape slot algorithm '%s' is not being run." % self.slots.shape)
        for slot in (self.slots.psfFlux, self.slots.apFlux, self.slots.modelFlux, self.slots.instFlux):
            if slot is not None:
                for name in self.algorithms.names:
                    if len(name) <= len(slot) and name == slot[:len(name)]:
                        break
                else:
                    raise ValueError("source flux slot algorithm '%s' is not being run." % slot)
                

    def makeMeasureSources(self, schema, metadata=None):
        """ Convenience method to make a MeasureSources instance and
        fill it with the configured algorithms.

        This is defined in the Config class to support use in unit tests without needing
        to construct a Task object.
        """
        builder = algorithmsLib.MeasureSourcesBuilder(self.prefix if self.prefix is not None else "")
        if self.centroider.name is not None:
            builder.setCentroider(self.centroider.apply())
        builder.addAlgorithms(self.algorithms.apply())
        return builder.build(schema, metadata)

## \addtogroup LSST_task_documentation
## \{
## \page sourceMeasurementTask
## \ref SourceMeasurementTask_ "SourceMeasurementTask"
## \copybrief sourceMeasurementTask
## \}

class SourceMeasurementTask(pipeBase.Task):
    """!
\anchor SourceMeasurementTask_
\brief Measure the properties of sources on a single exposure.

\section meas_algorithms_measurement_Contents Contents

 - \ref meas_algorithms_measurement_Purpose
 - \ref meas_algorithms_measurement_Initialize
 - \ref meas_algorithms_measurement_IO
 - \ref meas_algorithms_measurement_Config
 - \ref meas_algorithms_measurement_Debug
 - \ref meas_algorithms_measurement_Example

\section meas_algorithms_measurement_Purpose	Description

\copybrief SourceMeasurementTask

\section meas_algorithms_measurement_Initialize	Task initialisation

\copydoc init

\section meas_algorithms_measurement_IO		Inputs/Outputs to the run method

\deprecated This Task's \c run method is currently called \c measure

\copydoc measure

\subsection SourceMeasurementTask_Hooks  Hooks called by measure

There are some additional methods available which are typically used to provide extra debugging information.
Schematically:
\code
    def measure(self, exposure, sources, ...):
        self.preMeasureHook(exposure, sources)

        self.preSingleMeasureHook(exposure, sources, -1)
        for i, source in enumerate(sources):
            self.preSingleMeasureHook(exposure, sources, i)
            self.measurer.apply(source, exposure) # Do the actual measuring
            self.postSingleMeasureHook(exposure, sources, i)

        self.postMeasureHook(exposure, sources)
\endcode

See SourceMeasurementTask.preMeasureHook, SourceMeasurementTask.preSingleMeasureHook,
SourceMeasurementTask.preSingleMeasureHook, SourceMeasurementTask.postSingleMeasureHook, and
SourceMeasurementTask.postMeasureHook.

\section meas_algorithms_measurement_Config       Configuration parameters

See \ref SourceMeasurementConfig

\section meas_algorithms_measurement_Debug		Debug variables

The \link lsst.pipe.base.cmdLineTask.CmdLineTask command line task\endlink interface supports a
flag \c -d to import \b debug.py from your \c PYTHONPATH; see \ref baseDebug for more about \b debug.py files.

The available variables in SourceMeasurementTask are:
<DL>
  <DT> \c display
  <DD>
  - If True, display the exposure on ds9's frame 0.  +ve detections in blue, -ve detections in cyan
  - Measured sources are labelled:
   - Objects deblended as PSFs with a * and other objects with a +
   - Brightest peak in red if parent else magenta
   - All other peaks in yellow
  - If display > 1, instead label each point by its ID and draw an error ellipse for its centroid
  - If display > 2, also print a table of (id, ix, iy) for all measured sources
</DL>

\section meas_algorithms_measurement_Example	A complete example of using SourceMeasurementTask

This code is in \link measAlgTasks.py\endlink in the examples directory, and can be run as \em e.g.
\code
examples/measAlgTasks.py --ds9
\endcode
\dontinclude measAlgTasks.py

See \ref meas_algorithms_detection_Example for a few more details on the DetectionTask.

Import the tasks (there are some other standard imports; read the file if you're confused)
\skip SourceDetectionTask
\until SourceMeasurementTask

We need to create our tasks before processing any data as the task constructors
can add extra columns to the schema.  First the detection task
\skipline makeMinimalSchema
\skip SourceDetectionTask.ConfigClass
\until detectionTask
and then the measurement task using the default algorithms (as set by SourceMeasurementConfig.algorithms):
\skipline SourceMeasurementTask.ConfigClass
\skip algMetadata
\until measureTask
(\c algMetadata is used to return information about the active algorithms).

We're now ready to process the data (we could loop over multiple exposures/catalogues using the same
task objects).  First create the output table and process the image to find sources:
\skipline afwTable
\skip result
\until sources

Then measure them:
\skipline measure

We then might plot the results (\em e.g. if you set \c --ds9 on the command line)
\skip display
\until RED

\dontinclude measAlgTasks.py
Rather than accept a default set you can select which algorithms should be run.
First create the Config object:
\skipline SourceMeasurementTask.ConfigClass
Then specify which algorithms we're interested in and set any needed parameters:
\until radii

Unfortunately that won't quite work as there are still "slots" (mappings between measurements like PSF fluxes
and the algorithms that calculate them) pointing to some of the discarded algorithms (see SourceSlotConfig,
\em e.g. SourceSlotConfig.psfFlux), so:

\skip instFlux
\until psfFlux
and create the task as before:
\skipline measureTask
We can find out what aperture radii were chosen with
\skipline radii
and add them to the display code:
\skip s in sources
\until YELLOW

and end up with something like
\image html measAlgTasks-ds9.png

<HR>
To investigate the \ref meas_algorithms_measurement_Debug, put something like
\code{.py}
    import lsstDebug
    def DebugInfo(name):
        di = lsstDebug.getInfo(name)        # N.b. lsstDebug.Info(name) would call us recursively
        if name == "lsst.meas.algorithms.measurement":
            di.display = 1

        return di

    lsstDebug.Info = DebugInfo
\endcode
into your debug.py file and run measAlgTasks.py with the \c --debug flag.
    """
    ConfigClass = SourceMeasurementConfig
    _DefaultName = "sourceMeasurement"
    TableVersion = 0

    def init(self, schema, algMetadata=None, **kwds):
        """!Create the task, adding necessary fields to the given schema.

        \param[in,out] schema        Schema object for measurement fields; will be modified in-place.
        \param[in,out] algMetadata   Passed to MeasureSources object to be filled with initialization
                                     metadata by algorithms (e.g. radii for aperture photometry).
        \param **kwds Keyword arguments passed to lsst.pipe.base.task.Task.__init__.
        """
        self.__init__(schema, algMetadata, **kwds)

    def __init__(self, schema, algMetadata=None, **kwds):
        """!Create the task, adding necessary fields to the given schema.

        \param[in,out] schema        Schema object for measurement fields; will be modified in-place.
        \param[in,out] algMetadata   Passed to MeasureSources object to be filled with initialization
                                     metadata by algorithms (e.g. radii for aperture photometry).
        \param         **kwds        Passed to Task.__init__.
        """
        pipeBase.Task.__init__(self, **kwds)
        self.measurer = self.config.makeMeasureSources(schema, algMetadata)
        if self.config.doReplaceWithNoise:
            self.makeSubtask('replaceWithNoise')

    def preMeasureHook(self, exposure, sources):
        '''!A hook, for debugging purposes, that is called at the start of the
        measure() method (before any noise replacement has occurred)
        \param exposure The Exposure being measured
        \param sources  The afwTable of Sources to set
        '''

        # pipe_base's Task provides self._display.
        if self._display:
            frame = 0
            ds9.mtv(exposure, title="input", frame=frame)

    def postMeasureHook(self, exposure, sources):
        '''!A hook, for debugging purposes, that is called at the end of the
        measure() method, after the sources have been returned to the Exposure.
        \param exposure The Exposure we just measured
        \param sources  The afwTable of Sources we just measured
        '''
        pass

    def preSingleMeasureHook(self, exposure, sources, i):
        '''!A hook, for debugging purposes, that is called immediately
        before the measurement algorithms for each source (after the Source's Footprint
        has been inserted into the Exposure)

        \param exposure The Exposure being measured
        \param sources  The afwTable of Sources being measured
        \param i        The index into sources of the Source we're about to measure

        Note that this will also be called with i=-1 just before entering the
        loop over measuring sources, *after* the sources have been replaced by noise (if noiseout is True).

        '''

        if self._display:
            if i < 0:
                # First time...
                try:
                    self.deblendAsPsfKey = sources.getSchema().find("deblend.deblended-as-psf").getKey()
                except KeyError:
                    self.deblendAsPsfKey = None
                    
            if self._display > 2 and i >= 0:
                peak = sources[i].getFootprint().getPeaks()[0]
                print "%-9d %4d %4d" % (sources[i].getId(), peak.getIx(), peak.getIy())

    def postSingleMeasureHook(self, exposure, sources, i):
        '''!A hook, for debugging purposes, that is called immediately after
        the measurement algorithms (before the Source has once again been replaced by noise)

        \param exposure The Exposure being measured
        \param sources  The afwTable of Sources being measured
        \param i        The index into sources of the Source we just measured
        '''
        self.postSingleMeasurementDisplay(exposure, sources[i])

    def postSingleMeasurementDisplay(self, exposure, source):
        '''!A hook, for debugging purposes, called by postSingleMeasureHook

        \param exposure The Exposure being measured
        \param source   The Source we just measured
        '''
        if self._display:
            if self._display > 1:
                ds9.dot(str(source.getId()), source.getX() + 2, source.getY(),
                        size=3, ctype=ds9.RED)
                cov = source.getCentroidErr()
                ds9.dot(("@:%.1f,%.1f,%1f" % (cov[0,0], cov[0,1], cov[1,1])),
                        *source.getCentroid(), size=3, ctype=ds9.RED)
                symb = "%d" % source.getId()
            else:
                symb = "*" if self.deblendAsPsfKey and source.get(self.deblendAsPsfKey) else "+"
                ds9.dot(symb, *source.getCentroid(), size=3,
                        ctype=ds9.RED if source.get("parent") == 0 else ds9.MAGENTA)

                for p in source.getFootprint().getPeaks():
                    ds9.dot("+", *p.getF(), size=0.5, ctype=ds9.YELLOW)
    
    @pipeBase.timeMethod
    def measure(self, exposure, sources, noiseImage=None, noiseMeanVar=None, references=None, refWcs=None):
        """!Measure sources on an exposure, with no aperture correction.

        \param[in]     exposure Exposure to process
        \param[in,out] sources  SourceCatalog containing sources detected on this exposure.
        \param[in]     noiseImage If 'config.doReplaceWithNoise = True', you can pass in
                       an Image containing noise.  This overrides the "config.noiseSource" setting.
        \param[in]     noiseMeanVar: if 'config.doReplaceWithNoise = True', you can specify
                       the mean and variance of the Gaussian noise that will be added, by passing
                       a tuple of (mean, variance) floats.  This overrides the "config.noiseSource"
                       setting (but is overridden by noiseImage).
        \param[in]     references SourceCatalog containing reference sources detected on reference exposure.
        \param[in]     refWcs     Wcs for the reference exposure.
        \return None
        """
        if references is None:
            references = [None] * len(sources)
        if len(sources) != len(references):
            raise RuntimeError("Number of sources (%d) and references (%d) don't match" %
                               (len(sources), len(references)))

        if self.config.doReplaceWithNoise and not hasattr(self, 'replaceWithNoise'):
            self.makeSubtask('replaceWithNoise')

        self.log.info("Measuring %d sources" % len(sources))
        self.config.slots.setupTable(sources.table, prefix=self.config.prefix)

        self.preMeasureHook(exposure, sources)

        # "noiseout": we will replace all the pixels within detected
        # Footprints with noise, and then add sources in one at a
        # time, measure them, then replace with noise again.  The idea
        # is that measurement algorithms might look outside the
        # Footprint, and we don't want other sources to interfere with
        # the measurements.  The faint wings of sources are still
        # there, but that's life.
        noiseout = self.config.doReplaceWithNoise
        if noiseout:
            self.replaceWithNoise.begin(exposure, sources, noiseImage, noiseMeanVar)
            # At this point the whole image should just look like noise.

        # Call the hook, with source id = -1, before we measure anything.
        # (this is *after* the sources have been replaced by noise, if noiseout)
        self.preSingleMeasureHook(exposure, sources, -1)

        with ds9.Buffering():
            for i, (source, ref) in enumerate(zip(sources, references)):
                if noiseout:
                    self.replaceWithNoise.insertSource(exposure, i)

                self.preSingleMeasureHook(exposure, sources, i)

                # Make the measurement
                if ref is None:
                    self.measurer.apply(source, exposure)
                else:
                    self.measurer.apply(source, exposure, ref, refWcs)

                self.postSingleMeasureHook(exposure, sources, i)

                if noiseout:
                    # Replace this source's pixels by noise again.
                    self.replaceWithNoise.removeSource(exposure, sources, source)

        if noiseout:
            # Put the exposure back the way it was
            self.replaceWithNoise.end(exposure, sources)

        self.postMeasureHook(exposure, sources)

    # Alias for backwards compatibility
    run = measure
