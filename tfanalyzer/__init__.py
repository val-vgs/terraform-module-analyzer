"""Terraform module analyzer package."""
from .models import ModuleInfo, ResourceInfo, TagAnalysis
from .resources import REQUIRED_TAGS, TAGGABLE_RESOURCES
from .analyzer import ModuleAnalyzer

__version__ = '0.1.0'
__all__ = ['ModuleAnalyzer', 'ModuleInfo', 'ResourceInfo', 'TagAnalysis', 
           'REQUIRED_TAGS', 'TAGGABLE_RESOURCES']