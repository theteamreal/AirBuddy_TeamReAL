import tensorflow as tf
import numpy as np
from PIL import Image
import os
import cv2
from .yolo_detector import get_yolo_detector

class CVAQIDetector:
    """Computer Vision AQI Detector - Analyzes images for pollution"""
    
    def __init__(self):
        self.model_path = os.path.join(os.path.dirname(__file__), 'ml_models', 'model.h5')
        self.model = None
        self.load_model()
    
    def load_model(self):
        """Load TensorFlow model"""
        try:
            if os.path.exists(self.model_path):
                # Suppress TensorFlow warnings
                os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
                tf.get_logger().setLevel('ERROR')
                
                self.model = tf.keras.models.load_model(self.model_path)
                self.model.compile(
                    optimizer='adam',
                    loss='mean_absolute_error',
                    metrics=['mean_squared_error', tf.keras.metrics.RootMeanSquaredError()]
                )
                print("✓ CV AQI model loaded successfully")
            else:
                print(f"⚠ Model not found at {self.model_path}")
                self.model = None
        except Exception as e:
            print(f"Error loading model: {e}")
            self.model = None
    
    def preprocess_image(self, image):
        """Preprocess image for model prediction"""
        # Resize to 200x200
        image = tf.image.resize(image, (200, 200))
        
        # Ensure 3 channels
        if image.shape[-1] == 1:
            image = tf.image.grayscale_to_rgb(image)
        elif image.shape[-1] != 3:
            image = tf.expand_dims(image, axis=-1)
            image = tf.image.grayscale_to_rgb(image)
        
        # Normalize
        image = image / 255.0
        
        # Crop to first 120 rows
        cropped_image = image[:120]
        
        # Ensure correct shape
        cropped_image = tf.ensure_shape(cropped_image, (120, 200, 3))
        
        return cropped_image
    
    def calculate_haziness(self, image_path):
        """Calculate haziness/visibility score using OpenCV"""
        try:
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                return 0.5
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Calculate variance of Laplacian (sharpness/blur detection)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Calculate brightness
            brightness = np.mean(gray)
            
            # Calculate contrast
            contrast = gray.std()
            
            # Haziness score (0 = clear, 1 = very hazy)
            # Low variance = blurry/hazy
            # High brightness + low contrast = hazy
            haziness = 1.0 - min(1.0, (laplacian_var / 500.0))
            
            # Adjust based on brightness and contrast
            if brightness > 180 and contrast < 30:
                haziness = min(1.0, haziness + 0.3)
            
            return round(haziness, 3)
            
        except Exception as e:
            print(f"Error calculating haziness: {e}")
            return 0.5
    
    def detect_pollution_source(self, image_path):
        """Detect type of pollution source from image characteristics"""
        try:
            img = cv2.imread(image_path)
            if img is None:
                return 'UNKNOWN'
            
            # Convert to HSV for better color detection
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            
            # Detect smoke (gray/white areas)
            lower_smoke = np.array([0, 0, 100])
            upper_smoke = np.array([180, 50, 255])
            smoke_mask = cv2.inRange(hsv, lower_smoke, upper_smoke)
            smoke_ratio = np.count_nonzero(smoke_mask) / smoke_mask.size
            
            # Detect dust (brown/yellow areas)
            lower_dust = np.array([10, 50, 50])
            upper_dust = np.array([30, 255, 255])
            dust_mask = cv2.inRange(hsv, lower_dust, upper_dust)
            dust_ratio = np.count_nonzero(dust_mask) / dust_mask.size
            
            # Detect fire/burning (red/orange areas)
            lower_fire = np.array([0, 100, 100])
            upper_fire = np.array([10, 255, 255])
            fire_mask = cv2.inRange(hsv, lower_fire, upper_fire)
            fire_ratio = np.count_nonzero(fire_mask) / fire_mask.size
            
            # Determine source
            if fire_ratio > 0.1:
                return 'FIRE'
            elif smoke_ratio > 0.3:
                return 'SMOKE'
            elif dust_ratio > 0.2:
                return 'DUST'
            elif smoke_ratio > 0.1:
                return 'VEHICLE'
            else:
                return 'UNKNOWN'
                
        except Exception as e:
            print(f"Error detecting pollution source: {e}")
            return 'UNKNOWN'
    
    def predict_aqi_from_image(self, image_path, base_aqi=None):
        """
        Main prediction function
        Returns: dict with prediction results
        """
        try:
            # Load and preprocess image
            uploaded_image = Image.open(image_path)
            uploaded_image = np.array(uploaded_image)
            preprocessed_image = self.preprocess_image(uploaded_image)
            
            # Expand dimensions for batch prediction
            preprocessed_image_expanded = tf.expand_dims(preprocessed_image, axis=0)
            
            # Predict using model
            if self.model:
                prediction = self.model.predict(preprocessed_image_expanded, verbose=0)
                model_aqi = int(prediction[0][0])
            else:
                # Fallback if model not available
                model_aqi = 150
            
            # Calculate haziness
            haziness_score = self.calculate_haziness(image_path)
            
            # Detect pollution source
            pollution_source = self.detect_pollution_source(image_path)
            
            # Calculate AQI rise based on haziness
            # Higher haziness = higher AQI increase
            aqi_rise = int(haziness_score * 100)
            
            # If base_aqi provided, calculate total AQI
            if base_aqi:
                predicted_aqi = min(500, base_aqi + aqi_rise)
            else:
                predicted_aqi = model_aqi
            
            # Determine health alert level
            if predicted_aqi <= 100:
                health_alert = 'LOW'
            elif predicted_aqi <= 200:
                health_alert = 'MODERATE'
            elif predicted_aqi <= 300:
                health_alert = 'HIGH'
            else:
                health_alert = 'SEVERE'
            
            return {
                'predicted_aqi': predicted_aqi,
                'base_aqi': base_aqi,
                'aqi_rise': aqi_rise,
                'haziness_score': haziness_score,
                'pollution_source': pollution_source,
                'health_alert_level': health_alert,
                'model_available': self.model is not None
            }
            
        except Exception as e:
            print(f"Error in prediction: {e}")
            return {
                'predicted_aqi': 150,
                'base_aqi': base_aqi,
                'aqi_rise': 0,
                'haziness_score': 0.5,
                'pollution_source': 'UNKNOWN',
                'health_alert_level': 'MODERATE',
                'model_available': False,
                'error': str(e)
            }


# Singleton instance
_detector = None

def get_detector():
    """Get or create detector instance"""
    global _detector
    if _detector is None:
        _detector = CVAQIDetector()
    return _detector

def predict_aqi_with_yolo(self, image_path, base_aqi=150):
    """
    Enhanced prediction combining CV haziness detection + YOLO object detection
    
    This method:
    1. Uses your existing haziness/smoke detection
    2. Adds YOLO vehicle/construction detection
    3. Combines both for final AQI prediction
    
    Args:
        image_path: Path to image file
        base_aqi: Current AQI from sensors
        
    Returns:
        dict with combined analysis
    """
    try:
        # 1. Get your existing CV detection (haziness/smoke)
        cv_result = self.predict_aqi_from_image(image_path, base_aqi)
        
        # 2. Get YOLO object detection (vehicles/construction)
        yolo_detector = get_yolo_detector()
        yolo_result = yolo_detector.detect_objects(image_path)
        
        # 3. Combine the results
        combined_aqi_rise = cv_result['aqi_rise']
        combined_source = cv_result['pollution_source']
        
        # Add vehicle pollution impact
        if yolo_result['has_vehicles']:
            vehicle_aqi_rise = yolo_result['aqi_rise']
            combined_aqi_rise += vehicle_aqi_rise
            
            # Update source if vehicles are significant
            if vehicle_aqi_rise > cv_result['aqi_rise']:
                combined_source = yolo_result['pollution_source']
            elif vehicle_aqi_rise > 20:
                # Both are significant - mention both
                if cv_result['pollution_source'] == 'SMOKE':
                    combined_source = 'SMOKE'  # Smoke is more critical
                else:
                    combined_source = yolo_result['pollution_source']
        
        # Calculate final predicted AQI
        predicted_aqi = min(500, base_aqi + combined_aqi_rise)
        
        # Determine health alert
        if predicted_aqi > 300:
            health_alert = 'SEVERE'
        elif predicted_aqi > 200:
            health_alert = 'HIGH'
        elif predicted_aqi > 150:
            health_alert = 'MODERATE'
        else:
            health_alert = 'LOW'
        
        return {
            # Combined results
            'predicted_aqi': predicted_aqi,
            'aqi_rise': combined_aqi_rise,
            'pollution_source': combined_source,
            'health_alert_level': health_alert,
            
            # CV detection details
            'haziness_score': cv_result['haziness_score'],
            'cv_pollution_source': cv_result['pollution_source'],
            'cv_aqi_rise': cv_result['aqi_rise'],
            
            # YOLO detection details
            'vehicle_count': yolo_result['vehicle_count'],
            'heavy_vehicle_count': yolo_result['heavy_vehicle_count'],
            'yolo_pollution_source': yolo_result['pollution_source'],
            'yolo_aqi_rise': yolo_result['aqi_rise'],
            'yolo_detections': yolo_result['detections'],
            
            # Metadata
            'base_aqi': base_aqi,
            'detection_method': 'CV + YOLO Combined',
            'success': True
        }
        
    except Exception as e:
        print(f"Error in combined prediction: {e}")
        # Fallback to CV-only prediction
        return self.predict_aqi_from_image(image_path, base_aqi)