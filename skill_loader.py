from dataclasses import dataclass, field
from typing import Dict, List, Optional
import os
import yaml

from logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class Skill:
    skill_name: str
    skill_content: str
    scripts_path: str


@dataclass
class SubAgentDef:
    agent_type: str
    description: str
    dependencies: List[str]
    mcp_modules: List[str]
    skill_content: str


class SkillMemory:
    """
    Skill 和 SubAgent 内存存储。
    """
    _skills: Dict[str, Skill] = {}
    _subagents: Dict[str, SubAgentDef] = {}
    
    @classmethod
    def add_skill(cls, skill: Skill) -> None:
        cls._skills[skill.skill_name] = skill
    
    @classmethod
    def add_subagent(cls, subagent: SubAgentDef) -> None:
        cls._subagents[subagent.agent_type] = subagent
    
    @classmethod
    def get_skill(cls, skill_name: str) -> Optional[Skill]:
        return cls._skills.get(skill_name)
    
    @classmethod
    def get_subagent(cls, agent_type: str) -> Optional[SubAgentDef]:
        return cls._subagents.get(agent_type)
    
    @classmethod
    def get_all_skills(cls) -> Dict[str, Skill]:
        return cls._skills
    
    @classmethod
    def get_all_subagents(cls) -> Dict[str, SubAgentDef]:
        return cls._subagents
    
    @classmethod
    def clear(cls) -> None:
        cls._skills = {}
        cls._subagents = {}


class SkillLoader:
    """从文件系统加载 skill 和 subagent 文档"""
    
    @staticmethod
    def load_skill(skill_dir: str) -> Skill:
        """
        从目录加载 skill
        
        Args:
            skill_dir: skill 目录路径
        
        Returns:
            Skill 对象
        """
        skill_name = os.path.basename(skill_dir)
        skill_md_path = os.path.join(skill_dir, "skill.md")
        
        if not os.path.exists(skill_md_path):
            raise FileNotFoundError(f"skill.md not found in {skill_dir}")
        
        with open(skill_md_path, 'r', encoding='utf-8') as f:
            skill_content = f.read()
        
        scripts_path = os.path.join(skill_dir, "scripts")
        if not os.path.exists(scripts_path):
            scripts_path = ""
        
        return Skill(
            skill_name=skill_name,
            skill_content=skill_content,
            scripts_path=scripts_path
        )
    
    @staticmethod
    def load_skills(skills_dir: str) -> Dict[str, Skill]:
        """
        扫描 skills 目录，加载所有 skill
        
        Args:
            skills_dir: skills 目录路径
        
        Returns:
            Dict[str, Skill]: skill_name -> Skill 映射
        """
        skills = {}
        if not os.path.exists(skills_dir):
            return skills
        
        for item in os.listdir(skills_dir):
            skill_dir = os.path.join(skills_dir, item)
            if os.path.isdir(skill_dir):
                skill_md = os.path.join(skill_dir, "skill.md")
                if os.path.exists(skill_md):
                    try:
                        skill = SkillLoader.load_skill(skill_dir)
                        skills[skill.skill_name] = skill
                    except Exception as e:
                        logger.warning(f"Failed to load skill from {skill_dir}: {e}")
        
        return skills
    
    @staticmethod
    def load_subagent(filepath: str, skills: Dict[str, Skill]) -> SubAgentDef:
        """
        从文件加载 SubAgent 定义
        
        Args:
            filepath: SubAgent 定义文件路径
            skills: 已加载的 skills 字典
        
        Returns:
            SubAgentDef 对象
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        metadata = SkillLoader.parse_metadata(content)
        
        agent_type = metadata.get("agent_type")
        dependencies = metadata.get("dependencies", [])
        
        for dep in dependencies:
            if dep not in skills:
                logger.warning(f"SubAgent {agent_type} depends on non-existent skill: {dep}")
        
        return SubAgentDef(
            agent_type=agent_type,
            description=metadata.get("description", ""),
            dependencies=dependencies,
            mcp_modules=metadata.get("mcp_modules", []),
            skill_content=content
        )
    
    @staticmethod
    def load_subagents(subagent_dir: str, skills: Dict[str, Skill]) -> Dict[str, SubAgentDef]:
        """
        扫描 subagent_skills 目录，加载所有 SubAgent 定义
        
        Args:
            subagent_dir: subagent_skills 目录路径
            skills: 已加载的 skills 字典
        
        Returns:
            Dict[str, SubAgentDef]: agent_type -> SubAgentDef 映射
        """
        subagents = {}
        if not os.path.exists(subagent_dir):
            return subagents
        
        for filename in os.listdir(subagent_dir):
            if filename.endswith("_subagent.md"):
                filepath = os.path.join(subagent_dir, filename)
                try:
                    subagent = SkillLoader.load_subagent(filepath, skills)
                    subagents[subagent.agent_type] = subagent
                except Exception as e:
                    print(f"Warning: Failed to load subagent from {filepath}: {e}")
        
        return subagents
    
    @staticmethod
    def parse_metadata(content: str) -> dict:
        """解析 skill.md 的 frontmatter 元数据"""
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1].strip()
                return yaml.safe_load(frontmatter) or {}
        return {}
    
    @staticmethod
    def scan_all(skills_dir: str, subagent_dir: str) -> None:
        """
        扫描并加载所有 skills 和 subagents 到 SkillMemory
        
        Args:
            skills_dir: skills 目录路径
            subagent_dir: subagent_skills 目录路径
        """
        skills = SkillLoader.load_skills(skills_dir)
        for skill in skills.values():
            SkillMemory.add_skill(skill)
        
        subagents = SkillLoader.load_subagents(subagent_dir, skills)
        for subagent in subagents.values():
            SkillMemory.add_subagent(subagent)
