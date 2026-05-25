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
        'cpu time': 'cpu_busy_time',
        'disk': 'disc',
        'disks': 'discs',
        'transaction': 'tmf',
        'transactions': 'tmf',
        'ipu': 'ipu',
        'oss cpu': 'osscpu',
        'oss ns': 'ossns',
        'oss name service': 'ossns',
        'file system': 'file',
        'filesystem': 'file',
    }
    
    # Domain detection keywords with scoring weights.
    # Vocabulary grounded in HPE NonStop Measure Reference Manual entity names
    # (CPU, DISC, DISCOPEN, DISKFILE, FILE, OSSNS, PROCESS, TMF, USERDEF) and the
    # enriched schema (backend/schema_store/enriched_schema.yaml).
    #
    # Weight 3 = highly specific (entity name, DDL record name, unique term).
    # Weight 2 = strong signal for this domain.
    # Weight 1 = generic / could overlap with other domains.
    DOMAIN_KEYWORDS = {
        'cpu': [
            ('cpu', 3), ('processor', 3), ('ipu', 3), ('zmscpu', 3),
            ('busy time', 3), ('cpu busy', 3), ('cpu_busy_time', 3),
            ('servernet', 3), ('svnet', 3),
            ('dispatch', 2), ('dispatcher', 2), ('scheduler', 2),
            ('memory', 2), ('swap', 2), ('paging', 2), ('page fault', 2),
            ('queue length', 2), ('ready queue', 2), ('interrupt', 2),
            ('utilization', 1), ('load', 1), ('page', 1),
        ],
        'disc': [
            ('disc', 3), ('disk', 3), ('discs', 3), ('disks', 3),
            ('zmsdisc', 3), ('dp2', 3), ('device name', 3),
            ('volume', 2), ('free space', 3), ('disk space', 3), ('disc space', 3),
            ('storage', 2), ('device', 2), ('mount', 2), ('partition', 2),
            ('cache hit', 2), ('cache miss', 2), ('cache level', 2),
            ('disc i/o', 2), ('disk i/o', 2),
        ],
        'dfile': [
            ('dfile', 3), ('diskfile', 3), ('disk file', 3), ('disc file', 3),
            ('zmsdfile', 3),
            ('per file', 2), ('per-file', 2), ('file extent', 2), ('extents', 2),
            ('file size', 2),
        ],
        'dopen': [
            ('dopen', 3), ('discopen', 3), ('diskopen', 3),
            ('disk open', 3), ('disc open', 3),
            ('opener', 3), ('openers', 3),
            ('file opener', 3), ('file openers', 3),
            ('opener statistics', 3), ('opener stats', 3), ('opener count', 3),
            ('zmsdopen', 3),
            ('who opened', 2), ('which process opened', 2),
            ('processes that opened', 2), ('opens per file', 2),
            ('per open', 2), ('per-opener', 2), ('open instance', 2),
            ('physical i/o', 2), ('physical io', 2),
        ],
        'file': [
            ('zmsfile', 3), ('dbio', 3),
            ('file activity', 3), ('file operations', 3), ('file ops', 3),
            ('file i/o', 3), ('file io', 3), ('logical i/o', 3), ('logical io', 3),
            ('file open', 2), ('file close', 2), ('file opens', 2), ('file closes', 2),
            ('file read', 2), ('file write', 2), ('file reads', 2), ('file writes', 2),
            # Post-abbreviation forms
            ('file reads', 2), ('file writes', 2),
            ('file system', 2), ('filesystem', 2),
            ('bytes read', 2), ('bytes written', 2),
            ('read count', 1), ('write count', 1),
        ],
        'proc': [
            ('process', 3), ('processes', 3), ('proc', 3), ('procs', 3),
            ('zmsproc', 3), ('pin', 3), ('process name', 3),
            ('program', 3), ('programs', 3), ('program name', 3),
            ('program file', 2), ('executable', 2), ('binary', 2),
            ('thread', 2), ('threads', 2),
            ('checkpoint', 2), ('ancestor', 2), ('creator', 2),
            ('parent process', 2), ('child process', 2),
            ('running process', 2), ('process state', 2), ('process status', 2),
            ('messaging', 1), ('cpu time', 1),
        ],
        'ossns': [
            ('ossns', 3), ('oss ns', 3), ('oss name service', 3),
            ('name service', 3), ('name server', 3), ('namespace', 3),
            ('zmsossns', 3),
            ('semaphore', 3), ('semaphores', 3),
            ('pipe server', 3), ('local server', 3),
            ('oss', 2), ('posix', 2), ('pathname', 2),
        ],
        'tmf': [
            ('tmf', 3), ('transaction', 3), ('transactions', 3),
            ('zmstmf', 3), ('$tmp', 3),
            ('audit trail', 3), ('audit dump', 3),
            ('backout', 3), ('backouts', 3),
            ('home transaction', 3), ('remote transaction', 3),
            ('commit', 2), ('committed', 2), ('aborted', 2), ('abort', 2),
            ('rollback', 2), ('two phase', 2), ('2pc', 2),
            ('tx', 2), ('txn', 2),
        ],
        'udef': [
            ('udef', 3), ('userdef', 3), ('user defined', 3), ('user-defined', 3),
            ('zmsudef', 3),
            ('custom metric', 3), ('custom metrics', 3),
            ('meascounterbump', 3), ('meascounterbumpinit', 3),
            ('user metric', 2), ('user counter', 2), ('custom counter', 2),
            ('application counter', 2),
        ],
    }

    # Threshold by which the top domain's score must exceed the runner-up for
    # the result to be treated as single-domain rather than 'multi'.
    DOMINANCE_RATIO = 1.5

    # When any of these comparison words appear AND at least two domains
    # scored above COMPARISON_DOMAIN_FLOOR, force 'multi'. Rationale:
    # phrasings like "compare X with Y" or "X vs Y" are explicit cross-domain
    # intent that pure keyword scoring misses when one side's tokens repeat.
    COMPARISON_TRIGGERS = [
        'compare', 'compared', 'comparison',
        'versus', ' vs ', ' vs. ',
        'alongside', 'side by side', 'side-by-side',
        'against',
    ]
    COMPARISON_DOMAIN_FLOOR = 2.0
    
    def __init__(self):
        """Initialize the normalizer and precompile keyword regexes."""
        self._compiled_keywords: Dict[str, list] = {}
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            compiled = []
            for keyword, weight in keywords:
                # Word-boundary match where the keyword begins/ends with a word char;
                # for tokens like 'i/o' or '$tmp' fall back to escaped substring with
                # surrounding non-word lookarounds so we still avoid partial overlap.
                if keyword[:1].isalnum() and keyword[-1:].isalnum():
                    pattern = r'\b' + re.escape(keyword) + r'\b'
                else:
                    pattern = r'(?<!\w)' + re.escape(keyword) + r'(?!\w)'
                compiled.append((re.compile(pattern), keyword, weight))
            self._compiled_keywords[domain] = compiled
    
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
        Detect the domain category from the query text using weighted keyword scoring.

        Each keyword carries an explicit weight (3=specific, 2=strong, 1=generic).
        Multi-word keywords additionally pick up a small bonus per extra token, so
        a phrase like "file opener" outscores the bare word "file".
        """
        domain_scores: Dict[str, float] = {}

        # Per domain: collect all keyword hits as (start, end, weight, keyword), then
        # drop any hit whose span is fully contained in a longer hit from the same
        # domain. This stops phrases like "disc space" from double-counting alongside
        # the bare "disc" keyword.
        for domain, compiled in self._compiled_keywords.items():
            hits = []
            for regex, keyword, weight in compiled:
                for m in regex.finditer(text):
                    hits.append((m.start(), m.end(), weight, keyword))
            if not hits:
                continue

            hits.sort(key=lambda h: (h[1] - h[0]), reverse=True)
            kept = []
            for start, end, weight, keyword in hits:
                if any(ks <= start and end <= ke for ks, ke, _, _ in kept):
                    continue
                kept.append((start, end, weight, keyword))

            score = 0.0
            for _, _, weight, keyword in kept:
                phrase_bonus = 1 + 0.25 * keyword.count(' ')
                score += weight * phrase_bonus
            if score > 0:
                domain_scores[domain] = score

        if not domain_scores:
            return 'multi'

        if len(domain_scores) == 1:
            return next(iter(domain_scores))

        # Comparison override: explicit cross-domain phrasing wins over scoring.
        # Keyword scoring double-counts a domain when its column name repeats
        # ("compare cpu_busy_time with per-process cpu_busy_time"), so check
        # the surface text for comparison intent before applying the ratio.
        if any(trigger in text for trigger in self.COMPARISON_TRIGGERS):
            qualifying = [d for d, s in domain_scores.items()
                          if s >= self.COMPARISON_DOMAIN_FLOOR]
            if len(qualifying) >= 2:
                return 'multi'

        sorted_items = sorted(domain_scores.items(), key=lambda kv: kv[1], reverse=True)
        top_domain, top_score = sorted_items[0]
        runner_up_score = sorted_items[1][1]

        if top_score >= runner_up_score * self.DOMINANCE_RATIO:
            return top_domain

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
        ("show opener statistics", "dopen", "DOPEN via 'opener' alone"),
        ("show file activity", "file", "FILE via 'file activity'"),
        ("who opened this file", "dopen", "DOPEN via 'who opened'"),
        ("logical i/o per process", "multi", "Ambiguous file+proc → multi"),
        ("audit trail backouts", "tmf", "TMF via audit/backout phrase"),
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
