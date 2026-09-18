from typing import List, Dict, Any, Optional
from data.base import AssetUniverse

class StaticAssetUniverse(AssetUniverse):
    """A static universe configured with a fixed list of eligible symbols."""
    def __init__(self, symbols: List[str]):
        self._symbols = symbols

    def get_eligible_assets(self) -> List[str]:
        return self._symbols
        
    def add_symbol(self, symbol: str):
        if symbol not in self._symbols:
            self._symbols.append(symbol)
            
    def remove_symbol(self, symbol: str):
        if symbol in self._symbols:
            self._symbols.remove(symbol)
