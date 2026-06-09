import yaml
import sys

with open('few_shots/examples.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

examples = data.get('examples', [])
print(f'Original count: {len(examples)}')

queries_to_keep = [
    'Show average CPU busy time per CPU',
    'Show comprehensive CPU performance metrics including type, memory, PCBs, queue lengths, busy percentages, overhead, swaps, dispatches, cache hits, and disk I/Os per second',
    'Show disk read and write counts per device',
    'List all process names with their CPU usage',
    'Show transaction backout counts',
    'Analyze CPU utilization with memory pressure and identify bottlenecks by correlating CPU busy time, page faults, and queue times across all CPUs',
    'Identify disk I/O hotspots by analyzing cache hit ratios, queue times, and correlating with file-level activity to find poorly cached files',
    'Perform deep process analysis correlating CPU usage, memory consumption, messaging activity, and file I/O to identify resource-intensive processes',
    'Analyze transaction performance by correlating TMF statistics with process activity and disk I/O to identify transaction bottlenecks and backout patterns',
    'Investigate file locking contention by analyzing lock wait times, blocked requests, and correlating with opener processes to identify lock conflicts',
    'Analyze OSS namespace server performance by correlating cache hit ratios, checkpoint activity, and semaphore contention with DP2 messaging patterns',
    'Perform comprehensive system health analysis by aggregating CPU, memory, disk, and process metrics to identify overall system bottlenecks and capacity issues',
    'Analyze disk cache effectiveness across all cache levels by calculating hit ratios, fault rates, and dirty block queue times to optimize cache configuration',
    'Identify messaging bottlenecks by analyzing inter-process communication patterns, queue times, and correlating with CPU and process activity',
    'Analyze file I/O patterns by correlating logical operations with physical disk I/O, cache behavior, and DBIO usage to identify optimization opportunities',
    'Average out all the server net values and show them to me',
    'Top 20 files by total physical I/O calls',
    'Count active opens per file and total requests across all openers',
    'List all distinct user-defined counter names and how many processes set each',
    'Top 20 files by logical reads + writes',
    'For each CPU show the interrupt busy percentage, backup disc process percentage, primary disc process percentage, other processes percentage, and user processes percentage — all as a fraction of delta time, ordered by CPU number'
]

filtered = [e for e in examples if e['query'] in queries_to_keep]

filtered.append({
    'domain': 'cpu',
    'query': 'Show the average CPU ready queue length per CPU, ensuring small values do not round to 0.',
    'sql': """SELECT
  cpu_num,
  CAST(SUM(cpu_qtime) * 1.0 / NULLIF(MAX(delta_time) * COUNT(DISTINCT from_timestamp), 0) AS NUMERIC(10,4)) AS avg_ready_queue_length
FROM macht413.cpu
GROUP BY cpu_num
ORDER BY avg_ready_queue_length DESC
LIMIT 10000;"""
})

data['examples'] = filtered
print(f'New count: {len(filtered)}')

class Dumper(yaml.Dumper):
    def increase_indent(self, flow=False, *args, **kwargs):
        return super().increase_indent(flow=flow, indentless=False)

with open('few_shots/examples.yaml', 'w', encoding='utf-8') as f:
    yaml.dump(data, f, sort_keys=False, width=1000, default_flow_style=False, Dumper=Dumper)
