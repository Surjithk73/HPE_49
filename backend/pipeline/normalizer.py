"""
Query Normalizer for QueryCraft
Normalizes user input and detects domain categories.
"""
import re
from typing import Dict, Tuple

class QueryNormalizer:
    """Normalizes natural language queries and detects domain categories."""
    
    # HPE NonStop abbreviation expansions
    ABBREVIATIONS = {
        'proc': 'process',
        'procs': 'processes',
        'util': 'utilization',
        'cpu busy': 'cpu_busy_time',
        'disk': 'disc',
        'disks': 'discs',
        'reads': 'reads_',
        'transaction': 'tmf',
        'transactions': 'tmf',
        'ipu': 'ipu',
        'oss cpu': 'osscpu',
        'oss ns': 'ossns',
        'oss name service': 'ossns',
        'file system': 'file',
        'filesystem': 'file',
    }
    
    # Domain detection keywords
    DOMAIN_KEYWORDS = {
        'cpu': ['cpu', 'processor', 'busy time', 'dispatch', 'memory', 'swap', 'page'],
        'disc': ['disc', 'disk', 'storage', 'free space', 'volume', 'device'],
        'dfile': ['disk file', 'diskfile', 'dfile'],
        'dopen': ['disk open', 'discopen', 'dopen', 'file opener', 'opener'],
        'file': ['file open', 'file close', 'dbio', 'file system', 'filesystem', 'file read', 'file write'],
        'proc': ['process', 'program', 'thread', 'checkpoint', 'ancestor', 'creator'],
        'ossns': ['ossns', 'oss ns', 'namespace', 'semaphore', 'pipe server', 'local server'],
        'tmf': ['tmf', 'transaction', 'backout', 'abort', 'commit', 'audit trail'],
        'udef': ['user defined', 'userdef', 'udef', 'custom metric'],
    }
    
    def __init__(self):
        """Initialize the normalizer."""
        pass
    
    def normalize(self, query: str) -> Dict[str, str]:
        """
        Normalize a user query.
        
        Args:
            query: Raw user input string
            
        Returns:
            Dictionary with 'normalized_text' and 'domain_category'
        """
        if not query or not query.strip():
            return {
                'normalized_text': '',
                'domain_category': 'multi'
            }
        
        # Step 1: Lowercase and strip
        normalized = query.lower().strip()
        
        # Step 2: Expand abbreviations
        normalized = self._expand_abbreviations(normalized)
        
        # Step 3: Detect domain category
        domain = self._detect_domain(normalized)
        
        return {
            'normalized_text': normalized,
            'domain_category': domain
        }
    
    def _expand_abbreviations(self, text: str) -> str:
        """
        Expand HPE NonStop abbreviations.
        
        Args:
            text: Input text
            
        Returns:
            Text with abbreviations expanded
        """
        result = text
        
        # Sort by length (longest first) to avoid partial replacements
        sorted_abbrevs = sorted(self.ABBREVIATIONS.items(), key=lambda x: len(x[0]), reverse=True)
        
        for abbrev, expansion in sorted_abbrevs:
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(abbrev) + r'\b'
            result = re.sub(pattern, expansion, result, flags=re.IGNORECASE)
        
        return result
    
    def _detect_domain(self, text: str) -> str:
        """
        Detect the domain category from the query text.
        
        Args:
            text: Normalized query text
            
        Returns:
            Domain category: one of the table names or 'multi'
        """
        # Count keyword matches per domain
        domain_scores = {}
        
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                # Count occurrences of each keyword
                if keyword in text:
                    score += text.count(keyword)
            
            if score > 0:
                domain_scores[domain] = score
        
        # If no matches, return 'multi'
        if not domain_scores:
            return 'multi'
        
        # If only one domain matched, return it
        if len(domain_scores) == 1:
            return list(domain_scores.keys())[0]
        
        # If multiple domains matched, check if one is significantly dominant
        max_score = max(domain_scores.values())
        top_domains = [d for d, s in domain_scores.items() if s == max_score]
        
        # If there's a clear winner (only one domain with max score), check if it's dominant
        if len(top_domains) == 1:
            # Check if the winner has at least 2x the score of the second place
            sorted_scores = sorted(domain_scores.values(), reverse=True)
            if len(sorted_scores) > 1 and sorted_scores[0] >= sorted_scores[1] * 2:
                return top_domains[0]
            # If scores are close, it's a multi-domain query
            return 'multi'
        
        # Multiple domains with same score = multi-domain query
        return 'multi'


# Unit tests
def run_tests():
    """Run unit tests for the normalizer."""
    print("Testing Query Normalizer...")
    print("=" * 60)
    
    normalizer = QueryNormalizer()
    
    test_cases = [
        # (input, expected_domain, description)
        ("Show CPU busy time for all CPUs", "cpu", "CPU domain"),
        ("disk reads per device", "disc", "Disc domain"),
        ("List all processes", "proc", "Process domain"),
        ("Show transaction backouts", "tmf", "TMF domain"),
        ("file opens and closes", "file", "File domain"),
        ("OSS namespace statistics", "ossns", "OSSNS domain"),
        ("user defined metrics", "udef", "UDEF domain"),
        ("show dfile statistics", "dfile", "DFILE domain"),
        ("file opener statistics", "dopen", "DOPEN domain"),
        ("show cpu and process data", "multi", "Multi-domain"),
        ("", "multi", "Empty query"),
    ]
    
    passed = 0
    failed = 0
    
    for query, expected_domain, description in test_cases:
        result = normalizer.normalize(query)
        actual_domain = result['domain_category']
        
        if actual_domain == expected_domain:
            print(f"✓ {description:30s}: '{query[:40]}...' → {actual_domain}")
            passed += 1
        else:
            print(f"✗ {description:30s}: Expected '{expected_domain}', got '{actual_domain}'")
            print(f"  Query: {query}")
            print(f"  Normalized: {result['normalized_text']}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Tests: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✓ All tests passed!")
    
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
