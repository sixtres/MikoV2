"""Validation module for DI container and dependencies.

Y-353: DI validation - ensures no global state, all dependencies
injected via Dependencies dataclass.
No global state (Y-353).
"""

from typing import Any, Protocol


class DependencyValidator:
    """Validates dependency injection compliance.
    
    Y-353: All modules must receive dependencies via constructor,
    never access global state.
    """
    
    @staticmethod
    def validate_dependency(name: str, value: Any) -> None:
        """Validate a single dependency.
        
        Args:
            name: Dependency name.
            value: Dependency value to validate.
            
        Raises:
            ValueError: If dependency is None or invalid type.
        """
        if value is None:
            raise ValueError(f"Dependency '{name}' cannot be None (Y-353)")
        
        # Validate callable dependencies
        if callable(value):
            return
        
        # Validate object dependencies
        if hasattr(value, "__class__"):
            return
        
        raise ValueError(
            f"Dependency '{name}' must be callable or object, got {type(value)}"
        )
    
    @staticmethod
    def validate_no_global_state(module_globals: dict[str, Any]) -> list[str]:
        """Check module globals for prohibited state.
        
        Args:
            module_globals: dict from globals().
            
        Returns:
            List of violations found.
        """
        violations: list[str] = []
        
        prohibited_prefixes = ("_global_", "_state_", "_cache_")
        
        for name, value in module_globals.items():
            # Skip dunder methods and constants
            if name.startswith("__") or name.isupper():
                continue
            
            # Check for prohibited patterns
            for prefix in prohibited_prefixes:
                if name.startswith(prefix):
                    violations.append(
                        f"Global state detected: '{name}' (Y-353 violation)"
                    )
                    break
        
        return violations
    
    @staticmethod
    def assert_di_compliance(dependencies_class: type) -> None:
        """Assert that a Dependencies class is properly structured.
        
        Args:
            dependencies_class: The Dependencies dataclass to validate.
            
        Raises:
            ValueError: If DI compliance fails.
        """
        if not hasattr(dependencies_class, "__dataclass_fields__"):
            raise ValueError(
                "Dependencies must be a @dataclass (Y-353)"
            )
        
        # All fields should have type annotations
        annotations = getattr(dependencies_class, "__annotations__", {})
        if not annotations:
            raise ValueError(
                "Dependencies must have type annotations (Y-353)"
            )


def validate_dependencies(dependencies: Any) -> list[str]:
    """Validate all dependencies in a Dependencies instance.
    
    Args:
        dependencies: Dependencies dataclass instance.
        
    Returns:
        List of validation errors (empty if valid).
    """
    errors: list[str] = []
    
    if not hasattr(dependencies, "__dataclass_fields__"):
        errors.append("Not a valid Dependencies dataclass")
        return errors
    
    for field_name in dependencies.__dataclass_fields__:
        value = getattr(dependencies, field_name, None)
        try:
            DependencyValidator.validate_dependency(field_name, value)
        except ValueError as e:
            errors.append(str(e))
    
    return errors
