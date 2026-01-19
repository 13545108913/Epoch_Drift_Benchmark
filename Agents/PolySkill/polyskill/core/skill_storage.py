"""
Skill Storage - Enhanced

Enhanced persistent storage and retrieval for induced skills with versioning and rollback support.
"""

import os
import json
import pickle
import shutil
import threading
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime
from contextlib import contextmanager
import logging

# Import new skill types
try:
    from .base import Skill, SkillType, SkillFormat, SkillMetadata
except ImportError:
    # Fallback for backward compatibility
    Skill = None
    SkillType = None
    SkillFormat = None
    SkillMetadata = None

logger = logging.getLogger(__name__)


class EnhancedSkillStorage:
    """
    Enhanced skill storage with versioning, rollback, and atomic operations.
    
    Features:
    - Support for new Skill objects and legacy dict format
    - Version tracking with rollback capability
    - Atomic operations with backup/restore
    - Enhanced search and filtering
    - Metadata management
    """
    
    def __init__(self, storage_path: str = "./learned_skills/"):
        """Initialize enhanced skill storage."""
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Storage structure
        self.skills_file = self.storage_path / "skills.json"
        self.versions_dir = self.storage_path / "versions"
        self.backups_dir = self.storage_path / "backups"
        self.code_dir = self.storage_path / "code"
        self.workflows_dir = self.storage_path / "workflows"
        self.patterns_dir = self.storage_path / "patterns"
        
        # Create directories
        for directory in [self.versions_dir, self.backups_dir, self.code_dir, 
                         self.workflows_dir, self.patterns_dir]:
            directory.mkdir(exist_ok=True)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Load database
        self.skills_db = self._load_skills_db()
        self.current_version = self.skills_db.get("version", 1)
        
    def _load_skills_db(self) -> Dict:
        """Load skills database with version support."""
        if self.skills_file.exists():
            try:
                with open(self.skills_file, 'r') as f:
                    db = json.load(f)
                
                # Migrate old format if needed
                if "version" not in db:
                    db = self._migrate_from_old_format(db)
                
                return db
            except Exception as e:
                logger.error(f"Error loading skills database: {e}")
                return self._create_empty_db()
        
        return self._create_empty_db()
    
    def _create_empty_db(self) -> Dict:
        """Create empty database structure."""
        return {
            "version": 1,
            "skills": [],
            "metadata": {
                "created": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "total_operations": 0
            },
            "indices": {
                "by_type": {},
                "by_name": {},
                "by_source": {}
            }
        }
    
    def _migrate_from_old_format(self, old_db: Dict) -> Dict:
        """Migrate from old SkillStorage format."""
        logger.info("Migrating from old skill storage format")
        
        new_db = self._create_empty_db()
        
        # Copy existing skills
        if "skills" in old_db:
            new_db["skills"] = old_db["skills"]
            
            # Add version info to existing skills
            for skill in new_db["skills"]:
                if "version" not in skill:
                    skill["version"] = 1
                if "updated" not in skill:
                    skill["updated"] = skill.get("created", datetime.now().isoformat())
        
        # Copy metadata
        if "metadata" in old_db:
            new_db["metadata"].update(old_db["metadata"])
        
        # Rebuild indices
        self._rebuild_indices(new_db)
        
        return new_db
    
    def store_skill(self, skill: Union[Skill, Dict[str, Any]]) -> bool:
        """
        Store a skill (new Skill object or legacy dict format).
        
        Args:
            skill: Skill object or dictionary
            
        Returns:
            True if stored successfully
        """
        with self._lock:
            try:
                # Convert to dict if Skill object
                if Skill and isinstance(skill, Skill):
                    skill_dict = self._skill_to_dict(skill)
                else:
                    skill_dict = skill.copy()
                
                # Create backup before modification
                backup_id = self._create_backup()
                
                try:
                    # Store skill with versioning
                    success = self._store_skill_internal(skill_dict)
                    
                    if success:
                        # Update version and metadata
                        self.current_version += 1
                        self._update_metadata()
                        self._save_skills_db()
                        logger.info(f"Stored skill: {skill_dict.get('name', 'unnamed')}")
                    else:
                        # Restore from backup on failure
                        self._restore_from_backup(backup_id)
                    
                    return success
                    
                except Exception as e:
                    logger.error(f"Error storing skill: {e}")
                    # Restore from backup
                    self._restore_from_backup(backup_id)
                    return False
                
            except Exception as e:
                logger.error(f"Failed to store skill: {e}")
                return False
    
    def _skill_to_dict(self, skill: Skill) -> Dict[str, Any]:
        """Convert Skill object to dictionary format."""
        return {
            "id": skill.id,
            "name": skill.name,
            "type": skill.skill_type.value if hasattr(skill.skill_type, 'value') else str(skill.skill_type),
            "format": skill.format.value if hasattr(skill.format, 'value') else str(skill.format),
            "content": skill.content,
            "description": skill.description,
            "task_examples": skill.task_examples,
            "metadata": skill.metadata.to_dict() if hasattr(skill.metadata, 'to_dict') else skill.metadata,
            "version": self.current_version + 1,
            "created": datetime.now().isoformat(),
            "updated": datetime.now().isoformat()
        }
    
    def _store_skill_internal(self, skill_dict: Dict[str, Any]) -> bool:
        """Internal skill storage logic."""
        # Generate unique ID if not present
        if "id" not in skill_dict or not skill_dict["id"]:
            skill_dict["id"] = self._generate_skill_id(skill_dict)
        
        # Check for existing skill with same ID
        existing_skill_idx = self._find_skill_index(skill_dict["id"])
        
        # Store content to appropriate directory
        file_path = self._store_skill_content(skill_dict)
        if not file_path:
            return False
        
        # Update skill entry
        skill_entry = {
            "id": skill_dict["id"],
            "name": skill_dict["name"],
            "type": skill_dict.get("type", "code"),
            "format": skill_dict.get("format", "python_function"),
            "description": skill_dict.get("description", ""),
            "file_path": str(file_path),
            "task_examples": skill_dict.get("task_examples", []),
            "metadata": skill_dict.get("metadata", {}),
            "version": skill_dict.get("version", self.current_version + 1),
            "created": skill_dict.get("created", datetime.now().isoformat()),
            "updated": datetime.now().isoformat()
        }
        
        if existing_skill_idx is not None:
            # Update existing skill
            old_skill = self.skills_db["skills"][existing_skill_idx]
            self._archive_skill_version(old_skill)
            self.skills_db["skills"][existing_skill_idx] = skill_entry
        else:
            # Add new skill
            self.skills_db["skills"].append(skill_entry)
        
        # Update indices
        self._update_indices(skill_entry)
        
        return True
    
    def _store_skill_content(self, skill_dict: Dict[str, Any]) -> Optional[Path]:
        """Store skill content to appropriate directory."""
        try:
            skill_type = skill_dict.get("type", "code")
            skill_format = skill_dict.get("format", "python_function")
            name = skill_dict["name"]
            content = skill_dict["content"]
            
            # Determine storage location
            if skill_type == "code" or skill_format == "python_function":
                file_path = self.code_dir / f"{name}.py"
            elif skill_type == "pattern" or skill_format == "action_sequence":
                file_path = self.patterns_dir / f"{name}.json"
                # Convert content to JSON if it's not already a string
                if not isinstance(content, str):
                    content = json.dumps(content, indent=2)
            else:
                file_path = self.workflows_dir / f"{name}.txt"
            
            # Write content
            with open(file_path, 'w') as f:
                if isinstance(content, str):
                    f.write(content)
                else:
                    f.write(str(content))
            
            return file_path
            
        except Exception as e:
            logger.error(f"Error storing skill content: {e}")
            return None
    
    def retrieve_skills(
        self,
        skill_type: Optional[str] = None,
        skill_format: Optional[str] = None,
        task_description: Optional[str] = None,
        source: Optional[str] = None,
        include_content: bool = True,
        limit: Optional[int] = None
    ) -> List[Union[Skill, Dict[str, Any]]]:
        """
        Enhanced skill retrieval with filtering options.
        
        Args:
            skill_type: Filter by skill type
            skill_format: Filter by skill format
            task_description: Filter by task similarity
            source: Filter by source (inducer type)
            include_content: Whether to load file content
            limit: Maximum number of results
            
        Returns:
            List of skills (Skill objects if available, otherwise dicts)
        """
        with self._lock:
            skills = self.skills_db["skills"].copy()
            
            # Apply filters
            if skill_type:
                skills = [s for s in skills if s.get("type") == skill_type]
            
            if skill_format:
                skills = [s for s in skills if s.get("format") == skill_format]
            
            if source:
                skills = [s for s in skills if s.get("metadata", {}).get("source") == source]
            
            if task_description:
                skills = self._filter_by_task_similarity(skills, task_description)
            
            # Sort by confidence/success rate
            skills.sort(
                key=lambda s: s.get("metadata", {}).get("confidence_score", 0), 
                reverse=True
            )
            
            # Apply limit
            if limit:
                skills = skills[:limit]
            
            # Load content if requested
            if include_content:
                for skill in skills:
                    file_path = Path(skill["file_path"])
                    if file_path.exists():
                        try:
                            with open(file_path, 'r') as f:
                                skill["content"] = f.read()
                        except Exception as e:
                            logger.error(f"Error loading content for skill {skill['id']}: {e}")
                            skill["content"] = ""
            
            # Convert to Skill objects if class is available
            if Skill:
                result = []
                for skill_dict in skills:
                    try:
                        skill_obj = self._dict_to_skill(skill_dict)
                        result.append(skill_obj)
                    except Exception as e:
                        logger.warning(f"Could not convert skill to object: {e}")
                        result.append(skill_dict)
                return result
            
            return skills
    
    def _dict_to_skill(self, skill_dict: Dict[str, Any]) -> Skill:
        """Convert dictionary to Skill object."""
        metadata = skill_dict.get("metadata", {})
        if isinstance(metadata, dict):
            metadata_obj = SkillMetadata(**metadata)
        else:
            metadata_obj = metadata
        
        return Skill(
            id=skill_dict["id"],
            name=skill_dict["name"],
            skill_type=SkillType(skill_dict.get("type", "code")),
            format=SkillFormat(skill_dict.get("format", "python_function")),
            content=skill_dict.get("content", ""),
            description=skill_dict.get("description", ""),
            task_examples=skill_dict.get("task_examples", []),
            metadata=metadata_obj
        )
    
    def _filter_by_task_similarity(
        self, 
        skills: List[Dict[str, Any]], 
        task_description: str
    ) -> List[Dict[str, Any]]:
        """Filter skills by task similarity."""
        task_words = set(task_description.lower().split())
        filtered_skills = []
        
        for skill in skills:
            # Check task examples
            for example in skill.get("task_examples", []):
                example_words = set(example.lower().split())
                overlap = task_words.intersection(example_words)
                
                if len(overlap) >= 2:  # At least 2 words in common
                    filtered_skills.append(skill)
                    break
        
        return filtered_skills
    
    def create_checkpoint(self, name: str) -> str:
        """Create a named checkpoint of current state."""
        with self._lock:
            checkpoint_id = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            checkpoint_path = self.versions_dir / f"checkpoint_{checkpoint_id}.json"
            
            # Save current state
            with open(checkpoint_path, 'w') as f:
                json.dump({
                    "checkpoint_id": checkpoint_id,
                    "version": self.current_version,
                    "skills_db": self.skills_db,
                    "created": datetime.now().isoformat()
                }, f, indent=2)
            
            logger.info(f"Created checkpoint: {checkpoint_id}")
            return checkpoint_id
    
    def rollback_to_checkpoint(self, checkpoint_id: str) -> bool:
        """Rollback to a previous checkpoint."""
        with self._lock:
            checkpoint_path = self.versions_dir / f"checkpoint_{checkpoint_id}.json"
            
            if not checkpoint_path.exists():
                logger.error(f"Checkpoint not found: {checkpoint_id}")
                return False
            
            try:
                # Load checkpoint
                with open(checkpoint_path, 'r') as f:
                    checkpoint_data = json.load(f)
                
                # Create backup of current state
                backup_id = self._create_backup()
                
                # Restore from checkpoint
                self.skills_db = checkpoint_data["skills_db"]
                self.current_version = checkpoint_data["version"]
                
                # Save restored state
                self._save_skills_db()
                
                logger.info(f"Rolled back to checkpoint: {checkpoint_id}")
                return True
                
            except Exception as e:
                logger.error(f"Error rolling back to checkpoint: {e}")
                return False
    
    def _create_backup(self) -> str:
        """Create backup of current state."""
        backup_id = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        backup_path = self.backups_dir / f"{backup_id}.json"
        
        with open(backup_path, 'w') as f:
            json.dump({
                "backup_id": backup_id,
                "version": self.current_version,
                "skills_db": self.skills_db,
                "created": datetime.now().isoformat()
            }, f, indent=2)
        
        return backup_id
    
    def _restore_from_backup(self, backup_id: str):
        """Restore from backup."""
        backup_path = self.backups_dir / f"{backup_id}.json"
        
        if backup_path.exists():
            try:
                with open(backup_path, 'r') as f:
                    backup_data = json.load(f)
                
                self.skills_db = backup_data["skills_db"]
                self.current_version = backup_data["version"]
                self._save_skills_db()
                
            except Exception as e:
                logger.error(f"Error restoring from backup: {e}")
    
    def _generate_skill_id(self, skill_dict: Dict[str, Any]) -> str:
        """Generate unique skill ID."""
        base_id = f"{skill_dict.get('type', 'skill')}_{skill_dict['name']}"
        
        # Check for conflicts
        counter = 1
        skill_id = base_id
        while any(s["id"] == skill_id for s in self.skills_db["skills"]):
            skill_id = f"{base_id}_{counter}"
            counter += 1
        
        return skill_id
    
    def _find_skill_index(self, skill_id: str) -> Optional[int]:
        """Find index of skill with given ID."""
        for i, skill in enumerate(self.skills_db["skills"]):
            if skill["id"] == skill_id:
                return i
        return None
    
    def _archive_skill_version(self, skill: Dict[str, Any]):
        """Archive old version of skill."""
        archive_path = self.versions_dir / f"skill_{skill['id']}_v{skill.get('version', 1)}.json"
        with open(archive_path, 'w') as f:
            json.dump(skill, f, indent=2)
    
    def _update_indices(self, skill: Dict[str, Any]):
        """Update search indices."""
        indices = self.skills_db["indices"]
        
        # By type
        skill_type = skill.get("type", "unknown")
        if skill_type not in indices["by_type"]:
            indices["by_type"][skill_type] = []
        if skill["id"] not in indices["by_type"][skill_type]:
            indices["by_type"][skill_type].append(skill["id"])
        
        # By name
        indices["by_name"][skill["name"]] = skill["id"]
        
        # By source
        source = skill.get("metadata", {}).get("source", "unknown")
        if source not in indices["by_source"]:
            indices["by_source"][source] = []
        if skill["id"] not in indices["by_source"][source]:
            indices["by_source"][source].append(skill["id"])
    
    def _rebuild_indices(self, db: Dict):
        """Rebuild all indices."""
        db["indices"] = {
            "by_type": {},
            "by_name": {},
            "by_source": {}
        }
        
        for skill in db["skills"]:
            self._update_indices(skill)
    
    def _update_metadata(self):
        """Update database metadata."""
        self.skills_db["metadata"]["last_updated"] = datetime.now().isoformat()
        self.skills_db["metadata"]["total_operations"] = self.skills_db["metadata"].get("total_operations", 0) + 1
        self.skills_db["version"] = self.current_version
    
    def _save_skills_db(self):
        """Save skills database atomically."""
        # Write to temporary file first
        temp_file = self.skills_file.with_suffix('.tmp')
        
        try:
            with open(temp_file, 'w') as f:
                json.dump(self.skills_db, f, indent=2)
            
            # Atomic move
            temp_file.replace(self.skills_file)
            
        except Exception as e:
            logger.error(f"Error saving skills database: {e}")
            if temp_file.exists():
                temp_file.unlink()
            raise
    
    def get_stats(self) -> Dict:
        """Get enhanced storage statistics."""
        with self._lock:
            stats = {
                "total_skills": len(self.skills_db["skills"]),
                "current_version": self.current_version,
                "storage_path": str(self.storage_path),
                "last_updated": self.skills_db["metadata"].get("last_updated"),
                "total_operations": self.skills_db["metadata"].get("total_operations", 0)
            }
            
            # Stats by type
            type_counts = {}
            source_counts = {}
            
            for skill in self.skills_db["skills"]:
                skill_type = skill.get("type", "unknown")
                type_counts[skill_type] = type_counts.get(skill_type, 0) + 1
                
                source = skill.get("metadata", {}).get("source", "unknown")
                source_counts[source] = source_counts.get(source, 0) + 1
            
            stats["by_type"] = type_counts
            stats["by_source"] = source_counts
            
            return stats
    
    # Legacy compatibility methods
    
    def store(self, skill: Dict[str, Any]) -> bool:
        """Legacy store method for backward compatibility."""
        return self.store_skill(skill)
    
    def retrieve(
        self,
        task_description: str = None,
        skill_type: str = None
    ) -> List[Dict[str, Any]]:
        """Legacy retrieve method for backward compatibility."""
        skills = self.retrieve_skills(
            skill_type=skill_type,
            task_description=task_description,
            include_content=True
        )
        
        # Convert Skill objects back to dicts for compatibility
        result = []
        for skill in skills:
            if Skill and isinstance(skill, Skill):
                result.append(skill.to_dict())
            else:
                result.append(skill)
        
        return result
    
    def export_all(self, formats: List[str]) -> Dict[str, str]:
        """Export all skills in specified formats."""
        export_paths = {}
        
        if "code" in formats:
            # Create Python module
            module_path = self.storage_path / "induced_actions.py"
            with open(module_path, 'w') as f:
                f.write("# Auto-generated induced actions\n")
                f.write(f"# Generated on {datetime.now().isoformat()}\n\n")
                
                code_skills = [s for s in self.skills_db["skills"] 
                             if s.get("type") == "code" or s.get("format") == "python_function"]
                
                for skill in code_skills:
                    file_path = Path(skill["file_path"])
                    if file_path.exists():
                        try:
                            with open(file_path, 'r') as sf:
                                f.write(f"# Skill: {skill['name']}\n")
                                f.write(f"# Source: {skill.get('metadata', {}).get('source', 'unknown')}\n")
                                f.write(sf.read() + "\n\n")
                        except Exception as e:
                            logger.error(f"Error exporting skill {skill['name']}: {e}")
            
            export_paths["code"] = str(module_path)
        
        if "natural_language" in formats:
            # Create workflows document
            doc_path = self.storage_path / "workflows.md"
            with open(doc_path, 'w') as f:
                f.write("# Induced Workflows\n\n")
                f.write(f"Generated on {datetime.now().isoformat()}\n\n")
                
                nl_skills = [s for s in self.skills_db["skills"] 
                           if s.get("type") == "natural_language" or s.get("format") == "natural_language"]
                
                for skill in nl_skills:
                    file_path = Path(skill["file_path"])
                    if file_path.exists():
                        try:
                            with open(file_path, 'r') as sf:
                                f.write(f"## {skill['name']}\n\n")
                                f.write(f"**Source:** {skill.get('metadata', {}).get('source', 'unknown')}\n\n")
                                f.write(f"**Description:** {skill.get('description', 'No description')}\n\n")
                                f.write(sf.read() + "\n\n---\n\n")
                        except Exception as e:
                            logger.error(f"Error exporting workflow {skill['name']}: {e}")
            
            export_paths["workflows"] = str(doc_path)
        
        return export_paths


# Maintain backward compatibility
SkillStorage = EnhancedSkillStorage