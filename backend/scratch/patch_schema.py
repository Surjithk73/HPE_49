import re

path = r'c:\Users\surji\HPE_CPP49\backend\schema_store\enriched_schema.yaml'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# For proc table
proc_append = '''
    interrupts:      { queryable: true, type: integer, counter_type: Incrementing, description: "Number of hardware interrupts processed by this process" }'''
text = re.sub(r'(tns_busy_time:.*?)\n', r'\1\n' + proc_append.strip('\n') + '\n', text)

# For file table
file_append = '''
    requests:       { queryable: true, type: integer, counter_type: Incrementing, description: "Number of requests to this file" }
    replies:        { queryable: true, type: integer, counter_type: Incrementing, description: "Number of replies sent" }
    request_qtime:  { queryable: true, type: integer, unit: microseconds, counter_type: Queue, description: "Time requests spent in queue" }
    reply_qtime:    { queryable: true, type: integer, unit: microseconds, counter_type: Queue, description: "Time replies spent in queue" }'''
text = re.sub(r'(waits:.*?)\n', r'\1\n' + file_append.strip('\n') + '\n', text)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
print('Patched schema.')
