// -*- LSST-C++ -*-
#if !defined(LSST_DETECTION_PSF_H)
#define LSST_DETECTION_PSF_H
//!
// Describe an image's PSF
//
#include <string>
#include <typeinfo>
#include "boost/shared_ptr.hpp"
#include "lsst/pex/exceptions.h"
#include "lsst/daf/data.h"
#include "lsst/afw/math.h"

namespace lsst {
namespace meas {
namespace algorithms {

class PsfFormatter;
class PsfFactoryBase;
/**
 * Create a particular sort of Psf.
 *
 * PsfT: the PSF class that we're going to instantiate
 * PsfFactorySignatureT: The signature of the PSF constructor
 *
 * \note We do NOT define the unspecialised type, as only a specific set of signatures are supported.  To add
 * another, you'll have to instantiate PsfFactory with the correct signature, add a suitable virtual member to
 * PsfFactoryBase, and add a matching createPSF function.
 */
template<typename PsfT, typename PsfFactorySignatureT> class PsfFactory;

/*!
 * \brief Represent an image's PSF
 *
 * \note A polymorphic base class for Psf%s
 */
class PSF : public lsst::daf::data::LsstBase, public lsst::daf::base::Persistable {
public:
    typedef boost::shared_ptr<PSF> Ptr; ///< shared_ptr to a PSF
    typedef boost::shared_ptr<const PSF> ConstPtr; ///< shared_ptr to a const PSF

    typedef lsst::afw::math::Kernel::Pixel Pixel; ///< Pixel type of Image returned by getImage
    typedef lsst::afw::image::Image<Pixel> Image; ///< Image type returned by getImage

    explicit PSF(int const width = 0, int const height = 0);
    explicit PSF(lsst::afw::math::Kernel::Ptr kernel);
    virtual ~PSF() = 0;
    /**
     * Register a factory that builds a type of PSF
     *
     * \note This function returns bool so that it can be used in an initialisation
     * at file scope to do the actual registration
     */
    template<typename PsfT, typename PsfFactorySignatureT>
    static bool registerMe(std::string const& name) {
        static bool _registered = false;
        
        if (!_registered) {
            PsfFactory<PsfT, PsfFactorySignatureT> *factory = new PsfFactory<PsfT, PsfFactorySignatureT>();
            factory->markPersistent();
            
            PSF::declare(name, factory);
            _registered = true;
        }

        return true;
    }
    
    ///
    /// Convolve an image with a Kernel
    ///
    template <typename ImageT>
    void convolve(ImageT& convolvedImage,     ///< convolved image
                  ImageT const& inImage,      ///< image to convolve
                  bool doNormalize = true,    ///< if True, normalize the kernel, else use "as is"
                  int edgeBit = -1            ///< mask bit to indicate pixel includes edge-extended data;
                  ///< if negative (default) then no bit is set; only relevant for MaskedImages
                 ) const {
        if (!getKernel() || getKernel()->getWidth() <= 0 || getKernel()->getHeight() <= 0) {
            throw LSST_EXCEPT(lsst::pex::exceptions::RuntimeErrorException,
                              "PSF does not have a realisation that can be used for convolution");            
        }
        lsst::afw::math::convolve(convolvedImage, inImage, *getKernel(), doNormalize, edgeBit);        
    }

    ///< Evaluate the PSF at (dx, dy)
    ///
    /// This routine merely calls doGetValue, but here we can provide default values
    /// for the virtual functions that do the real work
    ///
    double getValue(double const dx,            ///< Desired column (relative to centre of PSF)
                    double const dy,            ///< Desired row (relative to centre of PSF)
                    int xPositionInImage = 0,     ///< Desired column position in image (think "CCD")
                    int yPositionInImage = 0      ///< Desired row position in image (think "CCD")
                   ) const {
        return doGetValue(dx, dy, xPositionInImage, yPositionInImage);
    }

    virtual Image::Ptr getImage(double const x, double const y) const;

    void setKernel(lsst::afw::math::Kernel::Ptr kernel);
    lsst::afw::math::Kernel::Ptr getKernel();
    boost::shared_ptr<const lsst::afw::math::Kernel> getKernel() const;

    /// Set the number of columns that will be used for %image representations of the PSF
    void setWidth(int const width) const { _width = width; }
    /// Return the number of columns that will be used for %image representations of the PSF
    int getWidth() const { return _width; }
    /// Set the number of rows that will be used for %image representations of the PSF
    void setHeight(int const height) const { _height = height; }
    /// Return the number of rows that will be used for %image representations of the PSF
    int getHeight() const { return _height; }
    /// Return the PSF's (width, height)
    std::pair<int, int> getDimensions() const { return std::make_pair(_width, _height); }
protected:
    /*
     * Support for Psf factories
     */
#if !defined(SWIG)
    friend PSF::Ptr createPSF(std::string const& name,
                              int const width, int const height, double p0, double p1, double p2);
    friend PSF::Ptr createPSF(std::string const& name,
                              lsst::afw::math::Kernel::Ptr kernel);
#endif

    static void declare(std::string name, PsfFactoryBase* factory = NULL);
    static PsfFactoryBase& lookup(std::string name);
private:
    static PsfFactoryBase& _registry(std::string const& name, PsfFactoryBase * factory = NULL);
    LSST_PERSIST_FORMATTER(PsfFormatter)

    virtual double doGetValue(double const dx, double const dy,
                              int xPositionInImage, int yPositionInImage) const = 0;

    lsst::afw::math::Kernel::Ptr _kernel; // Kernel that corresponds to the PSF
    //
    // These are mutable as they are concerned with the realisation of getImage's image, not the PSF itself
    mutable int _width, _height;           // size of Image realisations of the PSF
};

/**
 * A polymorphic base class for Psf factories
 */
class PsfFactoryBase : public lsst::daf::base::Citizen {
public:
    PsfFactoryBase() : lsst::daf::base::Citizen(typeid(this)) {}
    virtual ~PsfFactoryBase() {}
    virtual PSF::Ptr create(int = 0, int = 0, double = 0, double = 0, double = 0) {
        throw LSST_EXCEPT(lsst::pex::exceptions::NotFoundException,
                          "This PSF type doesn't have an (int, int, double, double, double) constructor");
    };
    virtual PSF::Ptr create(lsst::afw::math::Kernel::Ptr) {
        throw LSST_EXCEPT(lsst::pex::exceptions::NotFoundException,
                          "This PSF type doesn't have a (lsst::afw::math::Kernel::Ptr) constructor");
    };
};
 
/**
 * Create a particular sort of Psf with signature (int, int, double, double, double)
 */
template<typename PsfT>
class PsfFactory<PsfT, boost::tuple<int, int, double, double, double> > : public PsfFactoryBase {
public:
    /**
     * Return a (shared_ptr to a) new PsfT
     */
    virtual PSF::Ptr create(int width = 0, int height = 0, double p0 = 0, double p1 = 0, double p2 = 0) {
        return typename PsfT::Ptr(new PsfT(width, height, p0, p1, p2));
    }
    /*
     * Call the other (non-implemented) create method to make icc happy
     */
    virtual PSF::Ptr create(lsst::afw::math::Kernel::Ptr ptr) {
        return PsfFactoryBase::create(ptr);
    };

};

/**
 * Create a particular sort of Psf with signature (lsst::afw::math::Kernel::Ptr)
 */
template<typename PsfT>
class PsfFactory<PsfT, lsst::afw::math::Kernel::Ptr> : public PsfFactoryBase {
public:
    /*
     * Call the other (non-implemented) create method to make icc happy
     */
    virtual PSF::Ptr create(int width = 0, int height = 0, double p0 = 0, double p1 = 0, double p2 = 0) {
        return PsfFactoryBase::create(width, height, p0, p1, p2);
    }
    /**
     * Return a (shared_ptr to a) new PsfT
     */
    virtual PSF::Ptr create(lsst::afw::math::Kernel::Ptr kernel) {
        return typename PsfT::Ptr(new PsfT(kernel));
    }
};

/************************************************************************************************************/
/**
 * Factory functions to return a PSF
 */
/**
 * Create a named sort of Psf with signature (int, int, double, double, double)
 */
PSF::Ptr createPSF(std::string const& type, int width = 0, int height = 0,
                   double = 0, double = 0, double = 0);

/**
 * Create a named sort of Psf with signature (lsst::afw::math::Kernel::Ptr)
 */
PSF::Ptr createPSF(std::string const& type, lsst::afw::math::Kernel::Ptr kernel);
}}}
#endif