#if !defined(LSST_MEAS_ALGORITHMS_SHAPE_H)
#define LSST_MEAS_ALGORITHMS_SHAPE_H 1
/**
 * @file
 */
#include <cmath>
#include <utility>
#include <string>
#include "boost/shared_ptr.hpp"
#include "boost/noncopyable.hpp"
#include "Eigen/Core"
#include "lsst/afw/image.h"
#include "lsst/meas/algorithms/Centroid.h"
#include "lsst/meas/algorithms/PSF.h"

namespace lsst { namespace meas { namespace algorithms {
/**
 * @brief Represent a position and its error
 */
class Shape {
public:
    typedef boost::shared_ptr<Shape> Ptr;
    typedef boost::shared_ptr<const Shape> ConstPtr;
    typedef Eigen::Matrix4f Matrix4;    // type for the 4x4 covariance matrix
    
    typedef std::pair<double, double> xyAndError;

    Shape(double m0=NAN, double mxx=NAN, double mxy=NAN, double myy=NAN, Centroid centroid=Centroid()) :
        _centroid(centroid),
        _m0(m0),
        _mxx(mxx), _mxy(mxy), _myy(myy),
        _covar(),
        _mxy4(NAN),
        _flags(0) {
    }
    ~Shape() {}

    Centroid& getCentroid() { return _centroid; } // this is doubtful design...
    Centroid const& getCentroid() const { return _centroid; }

    void setM0(double m0) { _m0 = m0; }
    double getM0() const { return _m0; }
    double getM0Err() const { return _covar(0, 0); }

    void setMxx(double mxx) { _mxx = mxx; }
    double getMxx() const { return _mxx; }
    double getMxxErr() const { return _covar(1, 1); }

    void setMxy(double mxy) { _mxy = mxy; }
    double getMxy() const { return _mxy; }
    double getMxyErr() const { return _covar(2, 2); }

    void setMyy(double myy) { _myy = myy; }
    double getMyy() const { return _myy; }
    double getMyyErr() const { return _covar(3, 3); }

    void setMxy4(double mxy4) { _mxy4 = mxy4; }
    double getMxy4() const { return _mxy4; }

    void setFlags(int flags) { _flags = flags; }
    int getFlags() const { return _flags; }

    void setCovar(Matrix4 covar) { _covar = covar; }
    const Matrix4& getCovar() const { return _covar; }
    
    double getE1() const;
    double getE1Err() const;
    double getE2() const;
    double getE2Err() const;
    double getE1E2Err() const;
    double getRms() const;
    double getRmsErr() const;
private:
    Centroid _centroid;                  // object's centroid, as measured along with moments
    double _m0;                           // 0-th moment
    double _mxx, _mxy, _myy;              // <xx> <xy> <yy>
    Matrix4 _covar;                      // covariance matrix for (_m0, _mxx, _mxy, _myy)
    double _mxy4;                         // 4th moment used for shear calibration
    int _flags;                          // flags describing processing
};

/**
 * Types of supported shape algorithms
 */
typedef int shapeType;

/**
 * @brief A pure virtual base class to calculate a shape
 *
 * Different implementations will use different algorithms
 */
template<typename ImageT>
class measureShape : public boost::noncopyable {
public:
    typedef boost::shared_ptr<measureShape> Ptr;
    typedef boost::shared_ptr<measureShape const> ConstPtr;

    measureShape() {}
    virtual ~measureShape() {}

    Shape apply(ImageT const& image, double xcen, double ycen,
                lsst::meas::algorithms::PSF const* psf=NULL, // fully qualified to make swig happy
                double background=0.0) const;

    static shapeType lookupType(std::string const& name);
protected:
    static void registerType(std::string const& name, shapeType type);
private:
    virtual Shape doApply(ImageT const& image, double xcen, double ycen, PSF const* psf, double background) const = 0;

    static std::map<std::string, shapeType>* _shapeTypes;
};

template<typename ImageT>
measureShape<ImageT>* createMeasureShape(std::string const& type);

}}}
#endif