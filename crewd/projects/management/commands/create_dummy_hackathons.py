from django.core.management.base import BaseCommand
from django.utils import timezone
from projects.models import Hackathon
from datetime import timedelta
import random

class Command(BaseCommand):
    help = 'Creates dummy hackathon data'

    def handle(self, *args, **kwargs):
        # Sample data for hackathons
        hackathon_data = [
            {
                'title': 'AI Innovation Challenge',
                'description': 'Build innovative AI solutions to solve real-world problems. Focus areas include natural language processing, computer vision, and machine learning applications.',
                'tags': 'Python, TensorFlow, PyTorch, Machine Learning, AI, Deep Learning',
                'prize_pool': 5000.00
            },
            {
                'title': 'Web3 DApp Development',
                'description': 'Create decentralized applications using blockchain technology. Build smart contracts, NFT marketplaces, or DeFi solutions.',
                'tags': 'Solidity, Ethereum, Web3.js, React, Smart Contracts, Blockchain',
                'prize_pool': 7500.00
            },
            {
                'title': 'Mobile App Innovation',
                'description': 'Design and develop innovative mobile applications that solve unique problems or provide entertainment value.',
                'tags': 'React Native, Flutter, iOS, Android, Mobile Development',
                'prize_pool': 3000.00
            },
            {
                'title': 'Cloud Solutions Hackathon',
                'description': 'Build scalable cloud solutions using modern cloud platforms. Focus on microservices, serverless architecture, and cloud-native applications.',
                'tags': 'AWS, Docker, Kubernetes, Microservices, Cloud Computing',
                'prize_pool': 6000.00
            },
            {
                'title': 'Sustainable Tech Challenge',
                'description': 'Develop technology solutions that promote sustainability and environmental conservation. Projects can include energy efficiency, waste management, or eco-friendly innovations.',
                'tags': 'IoT, Python, Data Science, Sustainability, Green Tech',
                'prize_pool': 4000.00
            }
        ]

        now = timezone.now()
        
        # Create hackathons with different statuses
        for i, data in enumerate(hackathon_data):
            # Alternate between different statuses
            if i % 3 == 0:
                # Upcoming hackathon
                start_date = now + timedelta(days=15)
                end_date = start_date + timedelta(days=2)
                registration_deadline = start_date - timedelta(days=2)
                status = 'upcoming'
            elif i % 3 == 1:
                # Ongoing hackathon
                start_date = now - timedelta(days=1)
                end_date = now + timedelta(days=1)
                registration_deadline = start_date - timedelta(days=2)
                status = 'ongoing'
            else:
                # Completed hackathon
                start_date = now - timedelta(days=30)
                end_date = start_date + timedelta(days=2)
                registration_deadline = start_date - timedelta(days=2)
                status = 'completed'

            hackathon = Hackathon.objects.create(
                title=data['title'],
                description=data['description'],
                start_date=start_date,
                end_date=end_date,
                max_team_size=random.randint(3, 5),
                prize_pool=data['prize_pool'],
                registration_deadline=registration_deadline,
                status=status,
                tags=data['tags']
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created hackathon "{hackathon.title}" ({status})')
            ) 