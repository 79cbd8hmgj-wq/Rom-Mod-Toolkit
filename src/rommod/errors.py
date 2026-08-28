"""Typed public exceptions for Rom Mod Toolkit."""


class RomModError(Exception):
    """Base error for toolkit operations."""


class ManifestError(RomModError):
    pass


class SourceMismatchError(RomModError):
    pass


class RomValidationError(RomModError):
    pass


class TargetNotFoundError(RomModError):
    pass


class PatchMismatchError(RomModError):
    pass


class AddressResolutionError(RomModError):
    pass


class ExternalToolError(RomModError):
    pass


class BuildError(RomModError):
    pass
