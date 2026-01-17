"""
Enhanced AQI Detector - Combines CV + YOLO
Save this as: main/enhanced_aqi_detector.py

This is SEPARATE from your existing cv_aqi_detector.py
It uses both detectors together
"""

from .cv_aqi_detector import get_detector as get_cv_detector

try:
    from .yolo_detector import get_yolo_detector
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("YOLO not available - using CV detection only")


class EnhancedAQIDetector:
    """
    Enhanced detector that combines:
    1. Your existing CV smoke/haze detection
    2. YOLO vehicle/object detection
    """
    
    def __init__(self):
        """Initialize both detectors"""
        # Get your existing CV detector
        self.cv_detector = get_cv_detector()
        
        # Get YOLO detector if available
        if YOLO_AVAILABLE:
            self.yolo_detector = get_yolo_detector()
        else:
            self.yolo_detector = None
    
    def predict_aqi_from_image(self, image_path, base_aqi=150):
        """
        Enhanced prediction using both CV and YOLO
        
        Args:
            image_path: Path to image file
            base_aqi: Current AQI from sensors
            
        Returns:
            dict with combined analysis including vehicle detection
        """
        try:
            # 1. Get CV detection (smoke/haze) from YOUR existing detector
            cv_result = self.cv_detector.predict_aqi_from_image(image_path, base_aqi)
            
            # 2. If YOLO not available, just return CV result
            if not YOLO_AVAILABLE or self.yolo_detector is None:
                print("Using CV detection only (YOLO not available)")
                return cv_result
            
            # 3. Get YOLO detection (vehicles/construction)
            yolo_result = self.yolo_detector.detect_objects(image_path)
            
            # 4. Combine the results
            combined_aqi_rise = cv_result['aqi_rise']
            combined_source = cv_result['pollution_source']
            
            # Add vehicle pollution impact if detected
            if yolo_result['has_vehicles']:
                vehicle_aqi_rise = yolo_result['aqi_rise']
                combined_aqi_rise += vehicle_aqi_rise
                
                # Determine which source is more significant
                if vehicle_aqi_rise > cv_result['aqi_rise']:
                    combined_source = yolo_result['pollution_source']
                elif vehicle_aqi_rise > 20:
                    # Both are significant
                    if cv_result['pollution_source'] == 'SMOKE':
                        combined_source = 'SMOKE'  # Smoke takes priority
                    else:
                        combined_source = yolo_result['pollution_source']
            
            # Calculate final predicted AQI
            predicted_aqi = min(500, base_aqi + combined_aqi_rise)
            
            # Determine health alert level
            if predicted_aqi > 300:
                health_alert = 'SEVERE'
            elif predicted_aqi > 200:
                health_alert = 'HIGH'
            elif predicted_aqi > 150:
                health_alert = 'MODERATE'
            else:
                health_alert = 'LOW'
            
            # Return combined result with ALL details
            return {
                # Final combined results
                'predicted_aqi': predicted_aqi,
                'aqi_rise': combined_aqi_rise,
                'pollution_source': combined_source,
                'health_alert_level': health_alert,
                
                # CV detection details (from YOUR existing system)
                'haziness_score': cv_result.get('haziness_score', 0),
                'cv_pollution_source': cv_result.get('pollution_source', 'UNKNOWN'),
                'cv_aqi_rise': cv_result.get('aqi_rise', 0),
                
                # YOLO detection details (NEW)
                'vehicle_count': yolo_result.get('vehicle_count', 0),
                'heavy_vehicle_count': yolo_result.get('heavy_vehicle_count', 0),
                'yolo_pollution_source': yolo_result.get('pollution_source'),
                'yolo_aqi_rise': yolo_result.get('aqi_rise', 0),
                'yolo_detections': yolo_result.get('detections', []),
                
                # Metadata
                'base_aqi': base_aqi,
                'detection_method': 'CV + YOLO Combined' if YOLO_AVAILABLE else 'CV Only',
                'success': True
            }
            
        except Exception as e:
            print(f"Error in enhanced prediction: {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback to CV-only prediction
            return self.cv_detector.predict_aqi_from_image(image_path, base_aqi)


# Singleton instance
_enhanced_detector_instance = None


def get_enhanced_detector():
    """
    Get singleton enhanced detector instance
    USE THIS in your views instead of get_detector()
    """
    global _enhanced_detector_instance
    if _enhanced_detector_instance is None:
        _enhanced_detector_instance = EnhancedAQIDetector()
    return _enhanced_detector_instance


# Convenience function
def predict_aqi_enhanced(image_path, base_aqi=150):
    """
    Quick function for enhanced AQI prediction
    """
    detector = get_enhanced_detector()
    return detector.predict_aqi_from_image(image_path, base_aqi)