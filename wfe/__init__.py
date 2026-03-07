"""QMS Workflow Engine - graph-based DAG workflow engine."""

from wfe.graph import Graph, Node, Field, Edge
from wfe.session import Session
from wfe.template import Template, TemplateLibrary, instantiate
from wfe.database import MockDatabase
from wfe.hooks import HookContext, HookResult, register, fire, REGISTRY

__all__ = [
    # Graph primitives
    "Graph", "Node", "Field", "Edge",
    # Session
    "Session",
    # Templates
    "Template", "TemplateLibrary", "instantiate",
    # Mock database
    "MockDatabase",
    # Hook infrastructure (implementations live in workflow_hooks.py)
    "HookContext", "HookResult", "register", "fire", "REGISTRY",
]
