from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from main.models import AQIData, AQIForecast, Policy, UserHealthProfile
from datetime import datetime, timedelta
import random

class Command(BaseCommand):
    help = 'Populate database with sample pollution and policy data'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Starting data population...'))
        
        # Delhi NCR areas
        areas = [
            'Connaught Place', 'Rohini', 'Dwarka', 'Noida Sector 62',
            'Gurgaon Cyber City', 'Anand Vihar', 'RK Puram', 'Nehru Place',
            'Lodhi Road', 'IGI Airport', 'Mayur Vihar', 'Vasant Kunj',
            'Faridabad', 'Ghaziabad', 'Greater Noida'
        ]
        
        # Create sample AQI data for each area
        self.stdout.write('Creating AQI data...')
        for area in areas:
            # Current data
            aqi_value = random.randint(150, 400)
            traffic = random.uniform(25, 50)
            industrial = random.uniform(10, 30)
            crop = random.uniform(15, 40)
            construction = random.uniform(10, 25)
            other = 100 - (traffic + industrial + crop + construction)
            
            AQIData.objects.create(
                area=area,
                aqi_value=aqi_value,
                pm25=random.uniform(50, 200),
                pm10=random.uniform(100, 400),
                traffic_contribution=traffic,
                industrial_contribution=industrial,
                crop_burning_contribution=crop,
                construction_contribution=construction,
                other_contribution=other,
                timestamp=datetime.now()
            )
            
            # Historical data (last 24 hours)
            for i in range(1, 25):
                past_time = datetime.now() - timedelta(hours=i)
                historical_aqi = aqi_value + random.randint(-50, 50)
                
                AQIData.objects.create(
                    area=area,
                    aqi_value=max(50, min(500, historical_aqi)),
                    pm25=random.uniform(40, 220),
                    pm10=random.uniform(90, 420),
                    traffic_contribution=traffic + random.uniform(-10, 10),
                    industrial_contribution=industrial + random.uniform(-5, 5),
                    crop_burning_contribution=crop + random.uniform(-10, 10),
                    construction_contribution=construction + random.uniform(-5, 5),
                    other_contribution=other + random.uniform(-5, 5),
                    timestamp=past_time
                )
        
        self.stdout.write(self.style.SUCCESS(f'Created AQI data for {len(areas)} areas'))
        
        # Create AQI forecasts
        self.stdout.write('Creating AQI forecasts...')
        forecast_count = 0
        for i in range(1, 73):  # 72 hours
            forecast_time = datetime.now() + timedelta(hours=i)
            
            # Create forecasts for random areas
            selected_areas = random.sample(areas, random.randint(5, 10))
            
            for area in selected_areas:
                base_aqi = random.randint(100, 350)
                # Add some pattern - worse in morning/evening rush hours
                hour = forecast_time.hour
                if 7 <= hour <= 10 or 18 <= hour <= 21:
                    base_aqi += random.randint(20, 50)
                
                AQIForecast.objects.create(
                    area=area,
                    forecast_date=forecast_time,
                    predicted_aqi=base_aqi,
                    confidence=random.uniform(0.7, 0.95)
                )
                forecast_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Created {forecast_count} forecasts'))
        
        # Create demo user with health profile
        self.stdout.write('Creating demo user...')
        try:
            demo_user = User.objects.create_user(
                username='demo',
                password='demo123',
                email='demo@pollution.platform'
            )
            
            UserHealthProfile.objects.create(
                user=demo_user,
                location='Connaught Place',
                has_respiratory_issues=True,
                has_allergies=True,
                is_elderly=False,
                is_child=False,
            )
            
            self.stdout.write(self.style.SUCCESS('Demo user created (username: demo, password: demo123)'))
        except:
            self.stdout.write(self.style.WARNING('Demo user already exists'))
        
        # Create sample policies
        self.stdout.write('Creating sample policies...')
        
        sample_policies = [
            {
                'title': 'Extend Odd-Even Traffic Rule to 6 Months',
                'description': 'Implement odd-even vehicle restrictions from October to March during high pollution season. Electric vehicles and emergency services exempted. Expected to reduce traffic-related pollution by 35-40%.',
                'policy_type': 'TRAFFIC',
            },
            {
                'title': 'Mandatory Construction Site Dust Control',
                'description': 'Require all construction sites to install water sprinklers, cover materials during transport, and use anti-dust sheets. Heavy fines for non-compliance. Will reduce construction dust by up to 60%.',
                'policy_type': 'CONSTRUCTION',
            },
            {
                'title': 'Complete Firecracker Ban Year-Round',
                'description': 'Prohibit manufacture, sale, and use of all firecrackers throughout the year. Focus on enforcement during festival seasons. Expected PM2.5 reduction of 20-30% during festivals.',
                'policy_type': 'FIRECRACKER',
            },
            {
                'title': 'Crop Residue Management Subsidy Program',
                'description': 'Provide 80% subsidy to farmers for purchasing modern equipment (Happy Seeder, Super SMS) for in-situ crop residue management. Target 50,000 farmers in NCR region.',
                'policy_type': 'CROP_BURNING',
            },
            {
                'title': 'Industrial Emission Monitoring System',
                'description': 'Install real-time emission monitoring devices in all industries. Automatic alerts when limits exceeded. Data accessible to public via dashboard. Reduce industrial pollution by 25-35%.',
                'policy_type': 'INDUSTRY',
            },
            {
                'title': 'Green Corridors for Public Transport',
                'description': 'Create dedicated bus lanes on major roads. Priority signals for buses. Increase metro frequency during peak hours. Expected to shift 15-20% private vehicle users to public transport.',
                'policy_type': 'TRAFFIC',
            },
            {
                'title': 'Weekend Construction Ban',
                'description': 'Prohibit all construction activities on weekends and public holidays in residential areas. Will provide 2-day weekly relief from construction dust.',
                'policy_type': 'CONSTRUCTION',
            },
        ]
        
        try:
            admin = User.objects.get(username='admin')
        except:
            try:
                admin = User.objects.first()
            except:
                admin = demo_user
        
        for policy_data in sample_policies:
            policy = Policy.objects.create(
                title=policy_data['title'],
                description=policy_data['description'],
                policy_type=policy_data['policy_type'],
                proposed_by=admin,
                status='PROPOSED',
                agree_count=random.randint(50, 500),
                disagree_count=random.randint(10, 100)
            )
        
        self.stdout.write(self.style.SUCCESS(f'Created {len(sample_policies)} sample policies'))
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== DATA POPULATION COMPLETE ==='))
        self.stdout.write(f'AQI Data Points: {AQIData.objects.count()}')
        self.stdout.write(f'Forecasts: {AQIForecast.objects.count()}')
        self.stdout.write(f'Policies: {Policy.objects.count()}')
        self.stdout.write(f'Users: {User.objects.count()}')
        self.stdout.write(self.style.SUCCESS('\nYou can now login with:'))
        self.stdout.write('Username: demo')
        self.stdout.write('Password: demo123')