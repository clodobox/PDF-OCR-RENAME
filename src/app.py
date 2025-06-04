#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import pikepdf
import ocrmypdf
from pdfminer.high_level import extract_text
from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
import yaml
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler


class ConfigurableRenamer:
    """Gère le renommage des fichiers selon la configuration."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.rename_config = config.get('rename', {})
        
    def extract_references(self, text: str) -> List[str]:
        """Extrait les références du texte selon les patterns configurés."""
        if not self.rename_config.get('enabled', True):
            return []
            
        matches = []
        
        # Appliquer tous les patterns de recherche
        for pattern_config in self.rename_config.get('search_patterns', []):
            pattern = pattern_config['pattern']
            flags_str = pattern_config.get('flags', '')
            
            # Construire les flags regex
            flags = 0
            if 'IGNORECASE' in flags_str:
                flags |= re.IGNORECASE
            if 'MULTILINE' in flags_str:
                flags |= re.MULTILINE
            if 'DOTALL' in flags_str:
                flags |= re.DOTALL
                
            found_matches = re.findall(pattern, text, flags)
            matches.extend(found_matches)
            
        return matches
        
    def clean_match(self, match: str) -> str:
        """Nettoie un match selon la configuration."""
        cleaning_config = self.rename_config.get('cleaning', {})
        
        # Supprimer les espaces si configuré
        if cleaning_config.get('remove_spaces', True):
            match = match.replace(' ', '')
            
        # Supprimer les caractères spéciaux
        for char in cleaning_config.get('remove_special_chars', []):
            match = match.replace(char, '')
            
        return match
        
    def apply_pre_extraction_corrections(self, match: str) -> str:
        """Applique les corrections avant l'extraction des parties."""
        corrections = self.rename_config.get('corrections', {}).get('pre_extraction', [])
        
        for correction in corrections:
            pattern = correction['pattern']
            replacement = correction['replacement']
            match = re.sub(pattern, replacement, match)
            
        return match
        
    def extract_parts(self, match: str) -> Optional[Dict[str, str]]:
        """Extrait les parties d'une référence selon le regex configuré."""
        extraction_config = self.rename_config.get('extraction', {})
        regex = extraction_config.get('regex', '')
        
        if not regex:
            return None
            
        parts_match = re.match(regex, match)
        if not parts_match:
            return None
            
        parts = {}
        groups_config = extraction_config.get('groups', {})
        
        for part_name, part_config in groups_config.items():
            index = part_config.get('index', 1)
            padding = part_config.get('padding', 0)
            padding_char = part_config.get('padding_char', '0')
            
            try:
                value = parts_match.group(index)
                if padding > 0:
                    if padding_char == '0' and value.isdigit():
                        value = value.zfill(padding)
                    else:
                        value = value.rjust(padding, padding_char)
                parts[part_name] = value
            except IndexError:
                logging.warning(f"Group {index} not found in match: {match}")
                return None
                
        return parts
        
    def apply_character_mapping(self, parts: Dict[str, str]) -> Dict[str, str]:
        """Applique le mapping de caractères pour corriger les erreurs OCR."""
        char_mapping = self.rename_config.get('corrections', {}).get('post_extraction', {}).get('character_mapping', {})
        
        for part_name, mappings in char_mapping.items():
            if part_name in parts:
                value = parts[part_name]
                for old_char, new_char in mappings.items():
                    value = value.replace(old_char, new_char)
                parts[part_name] = value
                
        return parts
        
    def apply_prefix_rules(self, parts: Dict[str, str]) -> Dict[str, str]:
        """Applique les règles spéciales basées sur le préfixe."""
        prefix_rules = self.rename_config.get('corrections', {}).get('post_extraction', {}).get('prefix_rules', [])
        
        for rule_set in prefix_rules:
            if parts.get('prefix') in rule_set.get('prefixes', []):
                for rule in rule_set.get('rules', []):
                    condition = rule.get('condition', '')
                    action = rule.get('action', '')
                    
                    # Évaluer la condition de manière sécurisée
                    try:
                        # Créer un contexte sécurisé pour eval
                        context = {
                            'prefix': parts.get('prefix', ''),
                            'middle': parts.get('middle', ''),
                            'suffix': parts.get('suffix', ''),
                        }
                        
                        if eval(condition, {"__builtins__": {}}, context):
                            # Exécuter l'action
                            exec(action, {"__builtins__": {}}, context)
                            # Mettre à jour les parts
                            for key in ['prefix', 'middle', 'suffix']:
                                if key in context and key in parts:
                                    parts[key] = context[key]
                    except Exception as e:
                        logging.error(f"Error applying prefix rule: {e}")
                        
        return parts
        
    def validate_reference(self, parts: Dict[str, str]) -> bool:
        """Valide une référence selon les règles configurées."""
        validation_config = self.rename_config.get('validation', {})
        
        # Vérifier les préfixes valides
        valid_prefixes = validation_config.get('valid_prefixes', [])
        if valid_prefixes and parts.get('prefix') not in valid_prefixes:
            return False
            
        # Appliquer les règles de validation
        for rule in validation_config.get('rules', []):
            field = rule.get('field')
            rule_type = rule.get('type')
            
            if field not in parts:
                continue
                
            value = parts[field]
            
            if rule_type == 'range' and value.isdigit():
                num_value = int(value)
                if num_value < rule.get('min', 0) or num_value > rule.get('max', 999999):
                    return False
                    
            elif rule_type == 'in_list':
                list_name = rule.get('list')
                valid_list = validation_config.get(list_name, [])
                if value not in valid_list:
                    return False
                    
        return True
        
    def format_reference(self, parts: Dict[str, str]) -> str:
        """Formate une référence selon le format de sortie configuré."""
        output_format = self.rename_config.get('extraction', {}).get('output_format', '{prefix}-{middle}-{suffix}')
        
        try:
            return output_format.format(**parts)
        except KeyError as e:
            logging.error(f"Missing part in format: {e}")
            return '-'.join(parts.values())
            
    def process_match(self, match: str) -> Optional[str]:
        """Traite un match complet selon toute la configuration."""
        # Nettoyer
        match = self.clean_match(match)
        
        # Appliquer les corrections pré-extraction
        match = self.apply_pre_extraction_corrections(match)
        
        # Extraire les parties
        parts = self.extract_parts(match)
        if not parts:
            return None
            
        # Appliquer le mapping de caractères
        parts = self.apply_character_mapping(parts)
        
        # Appliquer les règles basées sur le préfixe
        parts = self.apply_prefix_rules(parts)
        
        # Valider
        if not self.validate_reference(parts):
            return None
            
        # Formater
        return self.format_reference(parts)
        
    def generate_filename(self, references: List[str]) -> str:
        """Génère un nom de fichier à partir des références."""
        filename_config = self.rename_config.get('filename', {})
        
        # Appliquer la casse configurée
        case = filename_config.get('case', 'upper')
        if case == 'upper':
            references = [ref.upper() for ref in references]
        elif case == 'lower':
            references = [ref.lower() for ref in references]
            
        # Joindre avec le séparateur
        separator = filename_config.get('separator', '_')
        filename = separator.join(references)
        
        # Ajouter l'extension
        extension = filename_config.get('extension', '.pdf')
        filename += extension
        
        # Limiter la longueur
        max_length = filename_config.get('max_length', 150)
        if len(filename) > max_length:
            filename = filename[:max_length - len(extension)] + extension
            
        return filename


class PDFProcessor:
    def __init__(self, config_path: str = './config.yml'):
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
        
        self.ocr_config = self.config['ocr']
        self.renamer = ConfigurableRenamer(self.config)
        self.setup_logging()
        self.ensure_directories()
        
    def setup_logging(self):
        """Configure le système de logging."""
        log_config = self.config['logging']
        log_dir = Path(log_config['directory'])
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / log_config['filename']
        log_level = getattr(logging, log_config['level'].upper())
        log_format = log_config['format']
        
        if log_config['mode'] == 'daily':
            handler = TimedRotatingFileHandler(
                log_file, 
                when='midnight', 
                backupCount=log_config['backup_count']
            )
        else:
            handler = RotatingFileHandler(
                log_file, 
                maxBytes=log_config['max_size'], 
                backupCount=log_config['backup_count']
            )
        
        handler.setFormatter(logging.Formatter(log_format))
        
        logger = logging.getLogger()
        logger.setLevel(log_level)
        logger.addHandler(handler)
        
        # Ajout d'un handler console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(console_handler)
        
        self.clean_old_logs(log_dir, log_config['retention_days'])
        
    def clean_old_logs(self, log_dir: Path, retention_days: int):
        """Supprime les anciens fichiers de log."""
        now = datetime.now()
        for file in log_dir.glob('*.log*'):
            if file.is_file():
                modified_time = datetime.fromtimestamp(file.stat().st_mtime)
                if (now - modified_time).days > retention_days:
                    file.unlink()
                    logging.info(f"Deleted old log file: {file}")
                    
    def ensure_directories(self):
        """Crée les répertoires nécessaires s'ils n'existent pas."""
        directories = [
            self.ocr_config['input_directory'],
            self.ocr_config['output_directory'],
            self.ocr_config.get('backup_directory'),
            self.ocr_config.get('error_directory', 'error')
        ]
        
        for directory in directories:
            if directory:
                Path(directory).mkdir(parents=True, exist_ok=True)
                logging.info(f"Ensured directory exists: {directory}")
                
    def wait_for_file_ready(self, file_path: Path) -> bool:
        """Attend que le fichier soit prêt à être traité."""
        retries = self.ocr_config.get('retries_loading_file', 5)
        poll_seconds = self.ocr_config.get('poll_new_file_seconds', 5)
        
        for i in range(retries):
            try:
                with pikepdf.open(file_path) as pdf:
                    _ = len(pdf.pages)
                return True
            except (FileNotFoundError, pikepdf._core.PdfError, Exception) as e:
                if i == retries - 1:
                    logging.error(f"Failed to open {file_path} after {retries} attempts: {e}")
                    return False
                else:
                    logging.debug(f"File {file_path} not ready yet (attempt {i+1}/{retries})")
                    time.sleep(poll_seconds)
        return False
        
    def get_ocr_args(self) -> Dict[str, Any]:
        """Prépare les arguments pour OCRmyPDF."""
        ocr_args = {
            'language': self.ocr_config.get('language'),
            'image_dpi': self.ocr_config.get('image_dpi'),
            'use_threads': self.ocr_config.get('use_threads'),
            'author': self.ocr_config.get('author'),
            'subject': self.ocr_config.get('subject'),
            'rotate_pages': self.ocr_config.get('rotate_pages'),
            'remove_background': self.ocr_config.get('remove_background'),
            'deskew': self.ocr_config.get('deskew'),
            'oversample': self.ocr_config.get('oversample'),
            'optimize': self.ocr_config.get('optimize'),
            'tesseract_thresholding': self.ocr_config.get('tesseract_thresholding'),
            'tesseract_timeout': self.ocr_config.get('tesseract_timeout'),
            'rotate_pages_threshold': self.ocr_config.get('rotate_pages_threshold'),
            'pdfa_image_compression': self.ocr_config.get('pdfa_image_compression'),
            'progress_bar': self.ocr_config.get('progress_bar'),
            'jpg_quality': self.ocr_config.get('jpg_quality'),
            'png_quality': self.ocr_config.get('png_quality'),
            'jbig2_lossy': self.ocr_config.get('jbig2_lossy'),
            'jbig2_page_group_size': self.ocr_config.get('jbig2_page_group_size'),
            'tesseract_oem': self.ocr_config.get('tesseract_oem'),
            'force_ocr': self.ocr_config.get('force_ocr'),
        }
        
        ocr_args = {k: v for k, v in ocr_args.items() if v is not None}
        ocr_args.update(self.ocr_config.get('ocr_json_settings', {}))
        
        return ocr_args
        
    def execute_ocrmypdf(self, file_path: str):
        """Exécute OCRmyPDF sur le fichier."""
        file_path = Path(file_path)
        output_path = Path(self.ocr_config['output_directory']) / file_path.name
        
        logging.info("-" * 50)
        logging.info(f"Processing new file: {file_path}")
        
        if not self.wait_for_file_ready(file_path):
            self.move_to_error(file_path, "File not ready after retries")
            return
            
        # Backup si configuré
        if self.ocr_config.get('backup_directory'):
            backup_path = Path(self.ocr_config['backup_directory']) / file_path.name
            try:
                shutil.copy2(file_path, backup_path)
                logging.info(f"Backed up file to: {backup_path}")
            except Exception as e:
                logging.error(f"Failed to backup file: {e}")
                
        # Exécution OCR
        try:
            logging.info(f"Starting OCR process to: {output_path}")
            exit_code = ocrmypdf.ocr(
                input_file=str(file_path),
                output_file=str(output_path),
                **self.get_ocr_args()
            )
            
            if exit_code == 0:
                logging.info("OCR completed successfully")
                
                if self.ocr_config.get('on_success_delete', False):
                    file_path.unlink()
                    logging.info(f"Deleted original file: {file_path}")
                    
                # Renommer si configuré
                if self.config.get('rename', {}).get('enabled', True):
                    self.process_pdf_rename(output_path)
            else:
                logging.warning(f"OCR completed with exit code: {exit_code}")
                self.move_to_error(file_path, f"OCR exit code: {exit_code}")
                
        except Exception as e:
            logging.error(f"OCR failed with error: {e}")
            self.move_to_error(file_path, str(e))
            
    def move_to_error(self, file_path: Path, reason: str):
        """Déplace le fichier vers le dossier d'erreur."""
        error_dir = Path(self.ocr_config.get('error_directory', 'error'))
        error_dir.mkdir(exist_ok=True)
        
        try:
            dest = error_dir / file_path.name
            shutil.move(str(file_path), str(dest))
            logging.error(f"Moved file to error directory: {dest} (Reason: {reason})")
        except Exception as e:
            logging.error(f"Failed to move file to error directory: {e}")
            
    def process_pdf_rename(self, path: Path):
        """Renomme le PDF selon les patterns trouvés dans le texte."""
        try:
            logging.info(f"Starting rename process for: {path}")
            
            # Extraire le texte du PDF
            text = extract_text(str(path))
            
            # Extraire les références
            matches = self.renamer.extract_references(text)
            if not matches:
                logging.info("No patterns found in PDF")
                return
                
            # Traiter chaque match
            processed_refs = []
            for match in matches:
                processed = self.renamer.process_match(match)
                if processed:
                    processed_refs.append(processed)
                    
            if not processed_refs:
                logging.info("No valid references found after processing")
                return
                
            # Dédupliquer et trier
            processed_refs = sorted(list(set(processed_refs)))
            
            # Générer le nom de fichier
            new_filename = self.renamer.generate_filename(processed_refs)
            
            # Gérer les doublons
            output_dir = path.parent
            new_path = output_dir / new_filename
            
            if new_path.exists() and new_path != path:
                duplicate_format = self.config.get('rename', {}).get('filename', {}).get('duplicate_format', '({num})')
                base_name = new_filename.rsplit('.', 1)[0]
                extension = new_filename.rsplit('.', 1)[1]
                num = 1
                
                while True:
                    duplicate_name = f"{base_name}{duplicate_format.format(num=num)}.{extension}"
                    new_path = output_dir / duplicate_name
                    if not new_path.exists():
                        break
                    num += 1
                    
            # Renommer le fichier
            if new_path != path:
                path.rename(new_path)
                logging.info(f"Renamed file to: {new_path.name}")
            else:
                logging.info("File already has the correct name")
                
        except Exception as e:
            logging.error(f"Error during rename process: {e}")
            self.move_to_error(path, f"Rename error: {e}")


class PDFEventHandler(PatternMatchingEventHandler):
    def __init__(self, processor: PDFProcessor, patterns: List[str]):
        super().__init__(patterns=patterns)
        self.processor = processor
        
    def on_created(self, event):
        if not event.is_directory:
            logging.debug(f"New file detected: {event.src_path}")
            self.processor.execute_ocrmypdf(event.src_path)


def main():
    # Initialisation
    processor = PDFProcessor()
    
    # Configuration OCRmyPDF logging
    ocrmypdf.configure_logging(
        verbosity=(
            ocrmypdf.Verbosity.default
            if processor.ocr_config['loglevel'] != 'DEBUG'
            else ocrmypdf.Verbosity.debug
        ),
        manage_root_logger=True,
    )
    
    logging.info("Starting OCRmyPDF watcher service")
    logging.info(f"Input Directory: {processor.ocr_config['input_directory']}")
    logging.info(f"Output Directory: {processor.ocr_config['output_directory']}")
    
    # Vérifier la configuration
    if 'input_file' in processor.ocr_config.get('ocr_json_settings', {}):
        logging.error('ocr_json_settings should not specify input_file or output_file')
        sys.exit(1)
        
    # Configurer l'observateur
    handler = PDFEventHandler(processor, processor.ocr_config['patterns'])
    
    if processor.ocr_config.get('use_polling', False):
        observer = PollingObserver()
    else:
        observer = Observer()
        
    observer.schedule(
        handler, 
        processor.ocr_config['input_directory'], 
        recursive=False
    )
    
    # Démarrer l'observation
    observer.start()
    logging.info("Watching for new files...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutting down...")
        observer.stop()
    observer.join()
    logging.info("Service stopped")


if __name__ == "__main__":
    main()
