"""
YOLO-based Pollution Source Detector
ADD this as a NEW file: main/yolo_detector.py
"""

from ultralytics import YOLO
import cv2
import numpy as np
from pathlib import Path
import os


class YOLOPollutionDetector:
    """
    Detect pollution sources using YOLOv8 pre-trained model
    Detects: vehicles, trucks, buses, construction equipment, etc.
    """
    
    def __init__(self):
        """Initialize YOLO model"""
        try:
            # Use YOLOv8 nano (fastest) - will auto-download on first run
            self.model = YOLO('yolov8n.pt')
            print("✓ YOLO model loaded successfully")
            
            # Define pollution source categories from COCO dataset
            self.pollution_categories = {
                'vehicles': ['car', 'truck', 'bus', 'motorcycle', 'bicycle'],
                'construction': ['truck', 'train'],  # Large vehicles often construction
                'potential_industrial': ['train', 'truck'],
            }
            
            # AQI impact per detection
            self.aqi_impact = {
                'car': 3,
                'truck': 8,
                'bus': 10,
                'motorcycle': 2,
                'bicycle': 0,
                'train': 15,
            }
            
        except Exception as e:
            print(f"Error loading YOLO: {e}")
            self.model = None
    
    def detect_objects(self, image_path, confidence=0.25):
        """
        Detect objects in image
        
        Args:
            image_path: Path to image
            confidence: Detection confidence threshold (0-1)
            
        Returns:
            dict with detections and analysis
        """
        if self.model is None:
            return self._empty_result()
        
        try:
            # Run YOLO detection
            results = self.model(image_path, conf=confidence, verbose=False)
            
            detections = []
            vehicle_count = 0
            heavy_vehicle_count = 0
            total_aqi_impact = 0
            
            # Process detections
            for result in results:
                boxes = result.boxes
                
                for box in boxes:
                    class_id = int(box.cls[0])
                    class_name = result.names[class_id]
                    conf = float(box.conf[0])
                    bbox = box.xyxy[0].tolist()
                    
                    # Check if it's a pollution-related object
                    if class_name in ['car', 'truck', 'bus', 'motorcycle', 'bicycle', 'train']:
                        detections.append({
                            'class': class_name,
                            'confidence': round(conf, 2),
                            'bbox': bbox
                        })
                        
                        # Count vehicles
                        if class_name in self.pollution_categories['vehicles']:
                            vehicle_count += 1
                        
                        if class_name in ['truck', 'bus', 'train']:
                            heavy_vehicle_count += 1
                        
                        # Add to AQI impact
                        total_aqi_impact += self.aqi_impact.get(class_name, 0)
            
            # Determine pollution source
            pollution_source = self._determine_source(
                vehicle_count, 
                heavy_vehicle_count
            )
            
            # Calculate AQI rise
            aqi_rise = self._calculate_aqi_rise(
                vehicle_count,
                heavy_vehicle_count,
                total_aqi_impact
            )
            
            return {
                'detections': detections,
                'vehicle_count': vehicle_count,
                'heavy_vehicle_count': heavy_vehicle_count,
                'pollution_source': pollution_source,
                'aqi_rise': aqi_rise,
                'total_impact': total_aqi_impact,
                'has_vehicles': vehicle_count > 0,
                'success': True
            }
            
        except Exception as e:
            print(f"Error in YOLO detection: {e}")
            return self._empty_result()
    
    def _determine_source(self, vehicle_count, heavy_vehicle_count):
        """Determine primary pollution source"""
        if heavy_vehicle_count >= 3:
            return 'CONSTRUCTION'
        elif vehicle_count >= 10:
            return 'VEHICLE'
        elif vehicle_count >= 5:
            return 'VEHICLE'
        else:
            return None  # No significant vehicle pollution
    
    def _calculate_aqi_rise(self, vehicle_count, heavy_vehicle_count, total_impact):
        """Calculate estimated AQI rise from vehicles"""
        # Base calculation on total impact
        base_rise = total_impact
        
        # Add multiplier for congestion
        if vehicle_count > 20:
            base_rise *= 1.5  # Heavy traffic
        elif vehicle_count > 10:
            base_rise *= 1.2  # Moderate traffic
        
        # Cap at reasonable limits
        return min(int(base_rise), 100)
    
    def _empty_result(self):
        """Return empty result when detection fails"""
        return {
            'detections': [],
            'vehicle_count': 0,
            'heavy_vehicle_count': 0,
            'pollution_source': None,
            'aqi_rise': 0,
            'total_impact': 0,
            'has_vehicles': False,
            'success': False
        }
    
    def draw_detections(self, image_path, output_path=None):
        """
        Draw bounding boxes on image
        
        Args:
            image_path: Input image path
            output_path: Output image path (optional)
            
        Returns:
            Image with bounding boxes drawn
        """
        if self.model is None:
            return None
        
        try:
            # Run detection with plotting
            results = self.model(image_path, conf=0.25)
            
            for result in results:
                # Get plotted image
                img_with_boxes = result.plot()
                
                if output_path:
                    cv2.imwrite(output_path, img_with_boxes)
                
                return img_with_boxes
            
            return None
            
        except Exception as e:
            print(f"Error drawing detections: {e}")
            return None


# Singleton instance
_detector_instance = None

def get_yolo_detector():
    """Get singleton YOLO detector instance"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = YOLOPollutionDetector()
    return _detector_instance


# Convenience function
def detect_pollution_sources(image_path):
    """
    Quick function to detect pollution sources
    
    Args:
        image_path: Path to image
        
    Returns:
        Detection results dict
    """
    detector = get_yolo_detector()
    return detector.detect_objects(image_path)


if __name__ == "__main__":
    # Test the detector
    print("Testing YOLO Pollution Detector...")
    detector = YOLOPollutionDetector()
    
    test_image = "test_traffic.jpg"
    if os.path.exists(test_image):
        result = detector.detect_objects(test_image)
        print(f"\n=== Detection Results ===")
        print(f"Vehicles detected: {result['vehicle_count']}")
        print(f"Heavy vehicles: {result['heavy_vehicle_count']}")
        print(f"Pollution source: {result['pollution_source']}")
        print(f"Estimated AQI rise: +{result['aqi_rise']}")
        print(f"Total detections: {len(result['detections'])}")
    else:
        print(f"Test image not found: {test_image}")