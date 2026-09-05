# backend/services/i18n_service.py - COMPLETE FIXED
import json
import os
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class I18nService:
    """Internationalization service for multiple languages"""
    
    def __init__(self):
        self.default_language = 'en'
        self.supported_languages = [
            {'code': 'en', 'name': 'English', 'native_name': 'English', 'flag': '🇬🇧'},
            {'code': 'am', 'name': 'Amharic', 'native_name': 'አማርኛ', 'flag': '🇪🇹'},
            {'code': 'or', 'name': 'Oromo', 'native_name': 'Afaan Oromoo', 'flag': '🇪🇹'},
            {'code': 'ti', 'name': 'Tigrinya', 'native_name': 'ትግርኛ', 'flag': '🇪🇹'},
            {'code': 'so', 'name': 'Somali', 'native_name': 'Soomaali', 'flag': '🇪🇹'},
        ]
        self.translations = {}
        self._load_translations()
    
    def _load_translations(self):
        """Load translation files from translations directory"""
        translations_dir = os.path.join(settings.BASE_DIR, 'translations')
        os.makedirs(translations_dir, exist_ok=True)
        
        # Default translations if files don't exist
        default_translations = {
            'en': {
                'welcome': 'Welcome',
                'dashboard': 'Dashboard',
                'courses': 'Courses',
                'exams': 'Exams',
                'payments': 'Payments',
                'profile': 'Profile',
                'logout': 'Logout',
                'login': 'Login',
                'register': 'Register',
                'home': 'Home',
                'about': 'About',
                'contact': 'Contact',
                'search': 'Search',
                'settings': 'Settings',
                'notifications': 'Notifications',
                'grade': 'Grade',
                'cgpa': 'CGPA',
                'credits': 'Credits',
                'semester': 'Semester',
                'department': 'Department',
                'student_id': 'Student ID',
                'full_name': 'Full Name',
                'email': 'Email',
                'phone': 'Phone',
                'address': 'Address',
                'date_of_birth': 'Date of Birth',
                'gender': 'Gender',
                'male': 'Male',
                'female': 'Female',
                'other': 'Other',
                'save': 'Save',
                'cancel': 'Cancel',
                'delete': 'Delete',
                'edit': 'Edit',
                'view': 'View',
                'loading': 'Loading...',
                'error': 'Error',
                'success': 'Success',
                'warning': 'Warning',
                'info': 'Info',
                'yes': 'Yes',
                'no': 'No',
                'confirm': 'Confirm',
                'submit': 'Submit',
                'back': 'Back',
                'next': 'Next',
                'finish': 'Finish',
                'start': 'Start',
                'stop': 'Stop',
                'continue': 'Continue',
                'close': 'Close',
                'open': 'Open',
                'help': 'Help',
                'support': 'Support',
                'feedback': 'Feedback',
                'rating': 'Rating',
                'review': 'Review',
                'enroll': 'Enroll',
                'unenroll': 'Unenroll',
                'enrolled': 'Enrolled',
                'pending': 'Pending',
                'completed': 'Completed',
                'in_progress': 'In Progress',
                'overdue': 'Overdue',
                'verified': 'Verified',
                'rejected': 'Rejected',
                'locked': 'Locked',
                'unlocked': 'Unlocked',
                'active': 'Active',
                'inactive': 'Inactive',
                'published': 'Published',
                'draft': 'Draft',
                'live': 'Live',
                'upcoming': 'Upcoming',
                'past': 'Past',
                'ongoing': 'Ongoing',
                'total': 'Total',
                'average': 'Average',
                'score': 'Score',
                'marks': 'Marks',
                'percentage': 'Percentage',
                'pass': 'Pass',
                'fail': 'Fail',
                'passed': 'Passed',
                'failed': 'Failed',
                'excellent': 'Excellent',
                'good': 'Good',
                'fair': 'Fair',
                'poor': 'Poor',
                'grade_8_certificate': 'Grade 8 Certificate',
                'grade_12_certificate': 'Grade 12 Certificate',
                'transcript': 'Transcript',
                'other_documents': 'Other Documents',
                'upload': 'Upload',
                'download': 'Download',
                'print': 'Print',
                'share': 'Share',
                'copy': 'Copy',
                'paste': 'Paste',
                'cut': 'Cut',
                'undo': 'Undo',
                'redo': 'Redo',
                'refresh': 'Refresh',
                'filter': 'Filter',
                'sort': 'Sort',
                'export': 'Export',
                'import': 'Import',
                'backup': 'Backup',
                'restore': 'Restore',
                'maintenance': 'Maintenance',
                'system': 'System',
                'configuration': 'Configuration',
                'administration': 'Administration',
                'user_management': 'User Management',
                'course_management': 'Course Management',
                'exam_management': 'Exam Management',
                'payment_management': 'Payment Management',
                'report': 'Report',
                'analytics': 'Analytics',
                'statistics': 'Statistics',
                'logs': 'Logs',
                'audit': 'Audit',
                'security': 'Security',
                'permissions': 'Permissions',
                'roles': 'Roles',
                'departments': 'Departments',
                'teachers': 'Teachers',
                'students': 'Students',
                'admins': 'Admins',
                'finance': 'Finance',
                'registrar': 'Registrar',
                'department_head': 'Department Head',
                'chat': 'Chat',
                'messages': 'Messages',
                'online': 'Online',
                'offline': 'Offline',
                'typing': 'Typing...',
                'joined': 'Joined',
                'left': 'Left',
                'video_off': 'Video Off',
                'audio_off': 'Audio Off',
                'mute': 'Mute',
                'unmute': 'Unmute',
                'fullscreen': 'Fullscreen',
                'exit_fullscreen': 'Exit Fullscreen',
                'recording': 'Recording',
                'stop_recording': 'Stop Recording',
                'screen_share': 'Screen Share',
                'stop_sharing': 'Stop Sharing',
                'raise_hand': 'Raise Hand',
                'lower_hand': 'Lower Hand',
                'reaction': 'Reaction',
                'whiteboard': 'Whiteboard',
            },
            'am': {
                'welcome': 'እንኳን ደህና መጡ',
                'dashboard': 'ዳሽቦርድ',
                'courses': 'ኮርሶች',
                'exams': 'ፈተናዎች',
                'payments': 'ክፍያዎች',
                'profile': 'መገለጫ',
                'logout': 'ውጣ',
                'login': 'ግባ',
                'register': 'ተመዝገብ',
                'home': 'መነሻ',
                'about': 'ስለ እኛ',
                'contact': 'አግኙን',
                'search': 'ፈልግ',
                'settings': 'ቅንብሮች',
                'notifications': 'ማሳወቂያዎች',
                'grade': 'ውጤት',
                'cgpa': 'ሲጂፒኤ',
                'credits': 'ክሬዲቶች',
                'semester': 'ሴሚስተር',
                'department': 'መምሪያ',
                'student_id': 'የተማሪ መታወቂያ',
                'full_name': 'ሙሉ ስም',
                'email': 'ኢሜይል',
                'phone': 'ስልክ',
                'address': 'አድራሻ',
                'date_of_birth': 'የትውልድ ቀን',
                'gender': 'ጾታ',
                'male': 'ወንድ',
                'female': 'ሴት',
                'other': 'ሌላ',
                'save': 'ቆጥብ',
                'cancel': 'ሰርዝ',
                'delete': 'ሰርዝ',
                'edit': 'አርትዕ',
                'view': 'እይ',
                'loading': 'በመጫን ላይ...',
                'error': 'ስህተት',
                'success': 'ተሳካ',
                'warning': 'ማስጠንቀቂያ',
                'info': 'መረጃ',
                'yes': 'አዎ',
                'no': 'አይ',
                'confirm': 'አረጋግጥ',
                'submit': 'አስገባ',
                'back': 'ተመለስ',
                'next': 'ቀጥል',
                'finish': 'ጨርስ',
                'start': 'ጀምር',
                'stop': 'አቁም',
                'continue': 'ቀጥል',
                'close': 'ዝጋ',
                'open': 'ክፈት',
                'help': 'እገዛ',
                'support': 'ድጋፍ',
                'feedback': 'አስተያየት',
                'rating': 'ደረጃ',
                'review': 'ግምገማ',
                'enroll': 'ተመዝገብ',
                'unenroll': 'ውጣ',
                'enrolled': 'ተመዝግቧል',
                'pending': 'በመጠበቅ ላይ',
                'completed': 'ተጠናቋል',
                'in_progress': 'በሂደት ላይ',
                'overdue': 'ዘግይቷል',
                'verified': 'ተረጋግጧል',
                'rejected': 'ውድቅ ተደርጓል',
                'locked': 'ተቆልፏል',
                'unlocked': 'ተከፍቷል',
                'active': 'ንቁ',
                'inactive': 'ስራ ፈት',
                'published': 'ታትሟል',
                'draft': 'ረቂቅ',
                'live': 'በቀጥታ',
                'upcoming': 'በቅርቡ',
                'past': 'ያለፈ',
                'ongoing': 'በሂደት',
                'total': 'ጠቅላላ',
                'average': 'አማካይ',
                'score': 'ውጤት',
                'marks': 'ማርክ',
                'percentage': 'መቶኛ',
                'pass': 'ማለፍ',
                'fail': 'መውደቅ',
                'passed': 'አልፏል',
                'failed': 'ወድቋል',
                'excellent': 'በጣም ጥሩ',
                'good': 'ጥሩ',
                'fair': 'መጠነኛ',
                'poor': 'ደካማ',
            }
        }
        
        # Load or create translations
        for lang in self.supported_languages:
            code = lang['code']
            file_path = os.path.join(translations_dir, f'{code}.json')
            
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self.translations[code] = json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to load translations for {code}: {e}")
                    self.translations[code] = default_translations.get(code, {})
            else:
                # Create default translation file
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(default_translations.get(code, {}), f, ensure_ascii=False, indent=2)
                    self.translations[code] = default_translations.get(code, {})
                except Exception as e:
                    logger.warning(f"Failed to create translations for {code}: {e}")
                    self.translations[code] = {}
    
    def get_supported_languages(self):
        """Get list of supported languages"""
        return self.supported_languages
    
    def translate(self, key, language='en', **kwargs):
        """Translate a key to the specified language"""
        translations = self.translations.get(language, {})
        translation = translations.get(key, key)
        
        if kwargs:
            try:
                translation = translation.format(**kwargs)
            except:
                pass
        
        return translation
    
    def get_translation_file(self, language):
        """Get full translation file for a language"""
        return self.translations.get(language, {})
    
    def get_ui_strings(self, language='en'):
        """Get all UI strings for frontend"""
        return self.get_translation_file(language)

# Singleton
i18n_service = I18nService()