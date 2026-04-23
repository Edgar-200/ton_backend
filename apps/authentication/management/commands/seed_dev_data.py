"""
TON — Development Data Seeder

Creates a realistic seed dataset for local development and staging:
  - 1 admin user
  - 3 curated companies (Stage 1 — pre-verified)
  - 50 students (mix of verification states)
  - 30 active tasks across sectors
  - ~120 submissions with varied scores
  - 20 invitations (mix of statuses)
  - NikoScores seeded for all students

Usage:
  python manage.py seed_dev_data
  python manage.py seed_dev_data --clear   (wipe existing data first)

WARNING: Only run in development or staging. Never run against production.
"""

import random
import uuid
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.hashers import make_password


SECTORS = ['tech', 'engineering', 'business', 'agriculture', 'health']
COURSES = ['ict', 'civil_engineering', 'electrical', 'architecture', 'business', 'mechanical']
SKILL_TAGS_BY_SECTOR = {
    'tech': [['python', 'django'], ['react', 'javascript'], ['sql', 'data-analysis'], ['machine-learning']],
    'engineering': [['autocad', 'solidworks'], ['structural-analysis'], ['project-management']],
    'business': [['excel', 'financial-modeling'], ['market-research'], ['business-plan']],
    'agriculture': [['gis-mapping'], ['crop-analysis', 'excel'], ['supply-chain']],
    'health': [['data-entry', 'excel'], ['community-health'], ['health-informatics']],
}
COMPANY_DATA = [
    {'name': 'Buni Innovation Hub', 'brela': 'BR-DSM-001', 'sector': 'tech'},
    {'name': 'Vodacom Tanzania', 'brela': 'BR-DSM-002', 'sector': 'tech'},
    {'name': 'NMB Bank', 'brela': 'BR-DSM-003', 'sector': 'business'},
    {'name': 'Tanzania Breweries', 'brela': 'BR-DSM-004', 'sector': 'business'},
    {'name': 'TEMESA', 'brela': 'BR-DSM-005', 'sector': 'engineering'},
]
STUDENT_NAMES = [
    'Amina Hassan', 'Baraka Mwangi', 'Zawadi Kimani', 'Juma Rashid',
    'Fatuma Ally', 'Elias Mfaume', 'Grace Nyambo', 'Hassan Omari',
    'Irene Mwamba', 'Joel Maganga', 'Khadija Suleiman', 'Leonard Mushi',
    'Mary Minja', 'Naomi Swai', 'Omar Farouk', 'Pendo Chacha',
    'Rahma Juma', 'Salum Waziri', 'Tumaini Ndege', 'Upendo Komba',
    'Violet Masanja', 'William Tarimo', 'Xenia Mlay', 'Yusuf Bakar',
    'Zainab Mgaya', 'Abdallah Hamisi', 'Beatrice Mwita', 'Charles Lyimo',
    'Diana Shayo', 'Emmanuel Kajiru', 'Florence Lema', 'George Mcharo',
    'Helena Kimaro', 'Ibrahim Salum', 'Janet Mwakasege', 'Kelvin Mwenda',
    'Leila Ahmad', 'Mussa Tambwe', 'Nicholaus Massawe', 'Olivia Kessi',
    'Patrick Maro', 'Queenie Shirima', 'Robert Nkya', 'Sophia Meela',
    'Thomas Kileo', 'Ulrike Mwanga', 'Victoria Tesha', 'Wilson Mlowe',
    'Ximena Mwero', 'Yolanda Mhina',
]
TASK_TITLES = {
    'tech': [
        'Build a student attendance tracker in Python',
        'Create a REST API for a simple inventory system',
        'Analyze social media engagement data using pandas',
        'Design a mobile-responsive landing page',
        'Build a Django blog with user authentication',
        'Scrape and visualize DIT timetable data',
    ],
    'business': [
        'Conduct market research for SME financing in Dar es Salaam',
        'Create a 3-year financial model for a food kiosk',
        'Write a business plan for a campus delivery service',
        'Analyze customer churn data for a telecom company',
    ],
    'engineering': [
        'Design a water distribution network for a 50-unit estate',
        'Create an AutoCAD floor plan for a community health center',
        'Write a structural load analysis report for a 3-storey building',
    ],
    'agriculture': [
        'Map crop disease spread using GIS data',
        'Analyze supply chain inefficiencies for smallholder maize farmers',
    ],
    'health': [
        'Design a community health data collection form',
        'Analyze immunization coverage data for Dar es Salaam region',
    ],
}


class Command(BaseCommand):
    help = 'Seed development database with realistic TON data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all existing data before seeding.',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self._clear_data()

        self.stdout.write('Seeding development data...')

        admin = self._create_admin()
        companies = self._create_companies()
        students = self._create_students()
        tasks = self._create_tasks(companies)
        self._create_submissions(students, tasks)
        self._create_invitations(companies, students)
        self._seed_nikoscores(students)

        self.stdout.write(self.style.SUCCESS(
            f'\nSeed complete:\n'
            f'  1 admin (admin@ton.co.tz / admin123)\n'
            f'  {len(companies)} companies (password: company123)\n'
            f'  {len(students)} students (password: student123)\n'
            f'  {len(tasks)} tasks\n'
        ))

    def _clear_data(self):
        from apps.invitations.models import Invitation
        from apps.nikoscore.models import NikoScore, NikoScoreEvent
        from apps.tasks.models import Submission, Task
        from apps.companies.models import Company, Watchlist
        from apps.students.models import StudentProfile
        from apps.authentication.models import User

        self.stdout.write('Clearing existing seed data...')
        NikoScoreEvent.objects.all().delete()
        NikoScore.objects.all().delete()
        Invitation.objects.all().delete()
        Submission.objects.all().delete()
        Task.objects.all().delete()
        Watchlist.objects.all().delete()
        Company.objects.all().delete()
        StudentProfile.objects.all().delete()
        User.objects.filter(role__in=['student', 'company']).delete()

    def _create_admin(self):
        from apps.authentication.models import User
        user, _ = User.objects.get_or_create(
            email='admin@ton.co.tz',
            defaults={
                'role': 'admin',
                'is_staff': True,
                'is_superuser': True,
                'is_verified': True,
                'is_active': True,
            }
        )
        user.set_password('admin123')
        user.save()
        return user

    def _create_companies(self):
        from apps.authentication.models import User
        from apps.companies.models import Company

        companies = []
        for i, data in enumerate(COMPANY_DATA):
            email = f"{data['name'].lower().replace(' ', '.')}@company.co.tz"
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={'role': 'company', 'is_verified': True, 'is_active': True}
            )
            user.set_password('company123')
            user.save()

            company, _ = Company.objects.get_or_create(
                user=user,
                defaults={
                    'company_name': data['name'],
                    'brela_number': data['brela'],
                    'sector': data['sector'],
                    'contact_person': 'HR Manager',
                    'verification_status': 'verified',
                    'onboarding_stage': 1,
                }
            )
            companies.append(company)
        return companies

    def _create_students(self):
        from apps.authentication.models import User
        from apps.students.models import StudentProfile

        students = []
        ver_statuses = ['verified'] * 30 + ['pending'] * 10 + ['unsubmitted'] * 10

        for i, name in enumerate(STUDENT_NAMES):
            email = f"{name.lower().replace(' ', '.')}@student.dit.ac.tz"
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={
                    'role': 'student',
                    'is_verified': True,
                    'is_active': True,
                    'last_active_at': timezone.now() - timedelta(days=random.randint(0, 60)),
                }
            )
            user.set_password('student123')
            user.save()

            ver_status = ver_statuses[i % len(ver_statuses)]
            profile, _ = StudentProfile.objects.get_or_create(
                user=user,
                defaults={
                    'full_name': name,
                    'dit_student_id': f'DIT/2023/{i+1:04d}',
                    'course': random.choice(COURSES),
                    'year_of_study': random.randint(1, 4),
                    'bio': (
                        f'I am {name}, a passionate student at DIT with strong interest in '
                        f'technology and problem-solving. I am looking for opportunities to '
                        f'apply my academic knowledge to real-world challenges and grow professionally. '
                        f'My goal is to contribute meaningfully to Tanzania\'s digital economy.'
                    ),
                    'profile_photo_url': f'https://res.cloudinary.com/ton-dev/image/upload/student_{i+1}.jpg',
                    'sectors': random.sample(SECTORS, k=random.randint(2, 3)),
                    'verification_status': ver_status,
                }
            )
            students.append(profile)

        return students

    def _create_tasks(self, companies):
        from apps.tasks.models import Task

        tasks = []
        for company in companies:
            sector = company.sector
            titles = TASK_TITLES.get(sector, TASK_TITLES['tech'])
            for title in titles[:3]:  # 3 tasks per company
                task, _ = Task.objects.get_or_create(
                    company=company,
                    title=title,
                    defaults={
                        'description': (
                            f'{title}. This is a real-world task designed to test your practical skills. '
                            f'You will need to demonstrate technical competence, clear communication, '
                            f'and professional presentation. Submit your work with a brief explanation '
                            f'of your approach and any assumptions you made. '
                            f'Quality will be assessed on accuracy, clarity, and completeness.'
                        ),
                        'sector': sector,
                        'skill_tags': random.choice(SKILL_TAGS_BY_SECTOR.get(sector, [['excel']])),
                        'deadline': timezone.now() + timedelta(days=random.randint(7, 30)),
                        'status': 'active',
                    }
                )
                tasks.append(task)

        return tasks

    def _create_submissions(self, students, tasks):
        from apps.tasks.models import Submission

        verified_students = [s for s in students if s.verification_status == 'verified']
        scores_pool = [None, None, 3, 3, 4, 4, 4, 5, 5, 5, 2, 1]

        for task in tasks:
            # Each task gets 3–8 submissions from random verified students
            submitters = random.sample(verified_students, k=min(random.randint(3, 8), len(verified_students)))
            for student in submitters:
                score = random.choice(scores_pool)
                reviewed_at = timezone.now() - timedelta(days=random.randint(1, 14)) if score else None
                Submission.objects.get_or_create(
                    task=task,
                    student=student,
                    defaults={
                        'content_text': (
                            f'Here is my submission for "{task.title}". '
                            f'I approached this problem by breaking it into smaller components. '
                            f'My solution demonstrates the core requirements and I have tested '
                            f'it against the provided criteria. Please find my detailed work attached.'
                        ),
                        'company_score': score,
                        'company_feedback': f'Good attempt. Solid understanding of the core requirements.' if score else '',
                        'status': 'reviewed' if score else 'submitted',
                        'reviewed_at': reviewed_at,
                        'nikoscore_processed': bool(score),
                    }
                )

            # Update cached counter
            task.submissions_count = task.submissions.count()
            task.save(update_fields=['submissions_count'])

    def _create_invitations(self, companies, students):
        from apps.invitations.models import Invitation

        verified_students = [s for s in students if s.verification_status == 'verified']
        statuses = ['sent', 'viewed', 'accepted', 'declined', 'accepted', 'accepted']

        for company in companies[:3]:
            sample = random.sample(verified_students, k=min(4, len(verified_students)))
            for student in sample:
                inv_status = random.choice(statuses)
                responded_at = timezone.now() - timedelta(days=random.randint(1, 7)) if inv_status in ['accepted', 'declined'] else None
                Invitation.objects.get_or_create(
                    company=company,
                    student=student,
                    defaults={
                        'invitation_type': random.choice(['internship', 'part_time', 'full_time']),
                        'message': (
                            f'Dear {student.full_name}, we have been following your work on TON '
                            f'and are impressed by your NikoScore and the quality of your submissions. '
                            f'We would love to discuss an opportunity with you at {company.company_name}.'
                        ),
                        'status': inv_status,
                        'contact_released': inv_status == 'accepted',
                        'responded_at': responded_at,
                        'expires_at': timezone.now() + timedelta(days=14),
                    }
                )

    def _seed_nikoscores(self, students):
        from apps.nikoscore.models import NikoScore

        for student in students:
            if student.verification_status == 'verified':
                profile_pts = 22
                activity_pts = random.randint(5, 20)
                quality_pts = random.randint(0, 20)
                reliability_pts = random.randint(8, 22)
            else:
                profile_pts = random.randint(0, 12)
                activity_pts = random.randint(0, 8)
                quality_pts = 0
                reliability_pts = random.randint(0, 5)

            total = min(100, profile_pts + activity_pts + quality_pts + reliability_pts)
            NikoScore.objects.update_or_create(
                student=student,
                defaults={
                    'total_score': total,
                    'component_profile': profile_pts,
                    'component_activity': activity_pts,
                    'component_quality': quality_pts,
                    'component_reliability': reliability_pts,
                }
            )
