"""
Language Detection and Translation Handler
Detects language and translates to English for analysis
"""

from langdetect import detect, DetectorFactory
from typing import Tuple, Dict

# Set seed for consistent language detection
DetectorFactory.seed = 0

class LanguageHandler:
    """Handle multilingual content - detection and translation"""
    
    SUPPORTED_LANGUAGES = {
        'en': 'English',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'pt': 'Portuguese',
        'ru': 'Russian',
        'ja': 'Japanese',
        'zh-cn': 'Chinese (Simplified)',
        'zh-tw': 'Chinese (Traditional)',
        'hi': 'Hindi',
        'ar': 'Arabic',
        'ko': 'Korean',
    }
    
    def __init__(self, translation_client=None):
        """
        Initialize language handler
        translation_client: NexusClient instance for translation
        """
        self.translation_client = translation_client
    
    def detect_language(self, text: str) -> Tuple[str, str]:
        """
        Detect language of given text
        Returns: (language_code, language_name)
        """
        try:
            if not text or len(text.strip()) < 10:
                return ('en', 'English')
            
            lang_code = detect(text)
            lang_name = self.SUPPORTED_LANGUAGES.get(lang_code, 'Unknown')
            return (lang_code, lang_name)
        except Exception as e:
            print(f"Language detection error: {e}")
            return ('en', 'English')
    
    def translate_to_english(self, text: str, source_language: str) -> Tuple[str, bool]:
        """
        Translate text to English if not already in English
        Returns: (translated_text, was_translated)
        """
        if source_language == 'en' or not self.translation_client:
            return (text, False)
        
        try:
            lang_name = self.SUPPORTED_LANGUAGES.get(source_language, source_language)
            translated = self.translation_client.translate_text(text, source_language, lang_name)
            return (translated, True)
        except Exception as e:
            print(f"Translation error: {e}")
            return (text, False)
    
    def process_content(self, content: str) -> Dict:
        """
        Process content for language and translation
        Returns dict with language info and translated content
        """
        lang_code, lang_name = self.detect_language(content)
        translated_content, was_translated = self.translate_to_english(content, lang_code)
        
        return {
            'original_language': lang_name,
            'language_code': lang_code,
            'was_translated': was_translated,
            'original_content': content,
            'processed_content': translated_content,
        }
    
    def process_batch(self, items: list) -> Dict:
        """
        Process multiple items (job description + resumes)
        items: list of strings
        Returns dict with language info for all items
        """
        results = []
        all_languages = set()
        
        for item in items:
            processed = self.process_content(item)
            results.append(processed)
            all_languages.add(processed['language_code'])
        
        return {
            'items': results,
            'detected_languages': list(all_languages),
            'needs_translation': len(all_languages) > 1 or 'en' not in all_languages,
        }
