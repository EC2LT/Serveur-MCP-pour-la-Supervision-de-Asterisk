# tools/__init__.py
from .supervision import register_supervision_tools
from .analysis import register_analysis_tools
from .control import register_control_tools


def register_all_tools(mcp):
    register_supervision_tools(mcp)
    register_analysis_tools(mcp)
    register_control_tools(mcp)
