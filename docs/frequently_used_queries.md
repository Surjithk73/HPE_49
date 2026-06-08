# Frequently Used HPE Queries

This document contains frequently used queries extracted from the `queries` folder.

## DISCCACHE_HITS
```sql
select  concat(device_name,'-',u_scsi_id_plpt_path,'-',cache_num) as disc_cache, avg(1000*1000*hits/delta_time) as hits_per_sec from $table group by 1 order by 2 desc limit 10
```

## DISCCACHE_INDIVIDUAL
```sql
select  concat(device_name,'-',u_scsi_id_plpt_path,'\:',cache_num) as disc_name, avg(cast(block_size as numeric)) as block_size, avg(cast(blks as numeric)) as blks, avg(cast(block_splits as numeric)) as block_splits, avg(cast(misses as numeric)) as misses, avg(cast(audit_buf_forces as numeric)) as audit_buf_forces, avg(cast(write_dirtys as numeric)) as write_dirtys, avg(cast(write_misses as numeric)) as write_misses from $table where lower(device_name)\=\#device_name and u_scsi_id_plpt_path\=\#u_scsi_id_plpt_path group by 1 order by 1
```

## DISCCACHE_MISSES
```sql
select  concat(device_name,'-',u_scsi_id_plpt_path,'-',cache_num) as disc_cache, avg(1000*1000*misses/delta_time) as misses_per_sec from $table group by 1 order by 2 desc limit 10
```

## DISCCACHE_OVERALL_VIEW
```sql
select  concat(device_name,'-',u_scsi_id_plpt_path,'\:',cache_num) as disc_name, avg(cast(block_size as numeric)) as block_size, avg(cast(blks as numeric)) as blks, avg(cast(block_splits as numeric)) as block_splits, avg(cast(hits as numeric)) as hits,avg(cast(misses as numeric)) as misses, avg(cast(audit_buf_forces as numeric)) as audit_buf_forces, avg(cast(write_dirtys as numeric)) as write_dirtys, avg(cast(write_misses as numeric)) as write_misses from $table group by 1 order by 1;
```

## DISC_BUSY_TIMES
```sql
select    concat(device_name,'-',u_scsi_id_plpt_path) as device_name, avg(100*cast(device_qbusy_time as numeric)/delta_time) as device_qbusy_time, avg(100*cast(read_qbusy_time as numeric)/delta_time) as read_qbusy_time, avg(100*cast(write_qbusy_time as numeric)/delta_time) as write_qbusy_time from $table group by 1  order by 2 desc limit 10
```

## DISC_DEVICE_AST
```sql
select    concat(device_name,'-',u_scsi_id_plpt_path) as device_name, avg(cast(device_qbusy_time as numeric)/delta_time)/(sum(cast(reads_ as numeric)/delta_time)+sum(cast(writes as numeric)/delta_time))/1000 as devive_ast from $table where cast(reads_ as numeric)\!\=0 or cast(writes as numeric)\!\=0 group by 1  order by 2 desc limit 10
```

## DISC_IO_BYTES
```sql
select    concat(device_name,'-',u_scsi_id_plpt_path) as device_name, avg(1000*1000*cast(input_bytes as numeric)/delta_time) as input_bytes, avg(1000*1000*cast(output_bytes as numeric)/delta_time) as output_bytes from $table group by 1  order by 2 desc limit 10
```

## DISC_QTIME
```sql
select    concat(device_name,'-',u_scsi_id_plpt_path) as device_name, avg(cast(read_qtime as numeric)/delta_time) as read_qtime, avg(cast(write_qtime as numeric)/delta_time) as write_qtime from $table group by 1  order by 2 desc limit 10
```

## DISC_REQUESTS
```sql
select    concat(device_name,'-',u_scsi_id_plpt_path) as device_name, avg(100*100*100*cast(requests as numeric)/delta_time) as requests from $table group by 1  order by 2 desc limit 10
```

## DISC_REQUEST_ART
```sql
select    concat(device_name,'-',u_scsi_id_plpt_path) as device_name, avg(cast(request_qtime as numeric)/delta_time)/avg(100*10*cast(requests as numeric)/delta_time) as request_art from $table where cast(requests as numeric)/delta_time \!\=0 group by 1  order by 2 desc limit 10
```

## DISC_REQUEST_QTIME
```sql
select    concat(device_name,'-',u_scsi_id_plpt_path) as device_name, avg(cast(request_qtime as numeric)/delta_time) as request_qtime_aql from $table group by 1  order by 2 desc limit 10
```

## DISC_VOLSEM_QTIME
```sql
select    concat(device_name,'-',u_scsi_id_plpt_path) as device_name, avg(cast(volsem_qtime   as numeric)/delta_time) as volsem_qtime_aql from $table group by 1  order by 2 desc limit 10
```

## DISKFILE_CACHE_RW
```sql
select   concat(file_name_volume,'.',file_name_subvol,'.',file_name_filename) as disk_file,  avg(cast(cache_write_hits as numeric)) as cache_write_hits, avg(cast(cache_read_hits as numeric)) as cache_read_hits from $table group by 1   order by 2 desc limit 10
```

## DISKFILE_DRIVER_INPUT_CALLS
```sql
select   concat(file_name_volume,'.',file_name_subvol,'.',file_name_filename) as disk_file,  avg(cast(driver_input_calls as numeric)) as driver_input_calls from $table group by 1   order by 2 desc   limit 10
```

## DISKFILE_DRIVER_OUTPUT_CALLS
```sql
select   concat(file_name_volume,'.',file_name_subvol,'.',file_name_filename) as disk_file,  avg(cast(driver_output_calls as numeric)) as driver_output_calls from $table group by 1   order by 2 desc   limit 10
```

## DISKFILE_OPEN_QTIME
```sql
select   concat(file_name_volume,'.',file_name_subvol,'.',file_name_filename) as disk_file, avg(open_qtime/delta_time) as open_qtime from $table group by 1 order by 2 desc limit 10
```

## DISKFILE_REQUESTS
```sql
select    concat(file_name_volume,'.',file_name_subvol,'.',file_name_filename) as disk_file,  avg(1000*1000*cast(requests as numeric)/delta_time) as requests  from $table group by 1  order by 2 desc  limit 10
```

## DISKFILE_TRANSIENT_OPENS
```sql
select   concat(file_name_volume,'.',file_name_subvol,'.',file_name_filename) as disk_file, avg(1000*100*cast(transient_opens as numeric)/delta_time) as open_qtime from $table group by 1 order by 2 desc limit 10
```

## Process_cpu_busy_time
```sql
select    concat(process.cpu_num,',',   process.pin,',',process.process_name ), process.cpu_busy_time    from     meas01.process where process.from_timestamp>'2017-12-03 21\:22\:44.526813'  and process.from_timestamp<'2017-12-03 21\:22\:46.526813' order by 2 desc limit 20
```

## PROCESS_DISPATCHES
```sql
select concat(process_name,'\:',cpu_num,',',pin) as "process-name", avg(dispatches*(1000*1000/delta_time)) as "dispatches" from $table group by 1 order by 2 desc limit 10;
```

## PROCESS_FILE_OPEN_CALLS
```sql
select concat(process_name,'\:',cpu_num,',',pin) as "process-name", avg(file_open_calls*(1000*1000/delta_time)) as "file_open_calls" from $table group by 1 order by 2 desc limit 10;
```

## PROCESS_INFO_CALLS
```sql
select concat(process_name,'\:',cpu_num,',',pin) as "process-name", avg(info_calls*(1000*1000/delta_time)) as "info_calls" from $table group by 1 order by 2 desc limit 10;
```

## PROCESS_MEM_QTIME
```sql
select concat(process_name,'\:',cpu_num,',',pin) as "process-name", avg(mem_qtime*( 100/delta_time)) as "mem_qtime" from $table group by 1 order by 2 desc limit 10;
```

## PROCESS_MESSAGES_RECEIVED
```sql
select concat(process_name,'\:',cpu_num,',',pin) as "process-name", avg(messages_received*(1000*1000/delta_time)) as "messages_received" from $table group by 1 order by 2 desc limit 10;
```

## PROCESS_MESSAGES_SENT
```sql
select concat(process_name,'\:',cpu_num,',',pin) as "process-name", avg(messages_sent*(1000*1000/delta_time)) as "messages_sent" from $table group by 1 order by 2 desc limit 10;
```

## PROCESS_MSGS_SENT_QTIME
```sql
select concat(process_name,'\:',cpu_num,',',pin) as "process-name", avg(msgs_sent_qtime*( 1/delta_time)) as "msgs_sent_qtime" from $table group by 1 order by 2 desc limit 10;
```

## PROCESS_PAGE_FAULTS
```sql
select concat(process_name,'\:',cpu_num,',',pin) as "process-name", avg(page_faults*(1000*1000/delta_time)) as "page_faults" from $table group by 1 order by 2 desc limit 10;
```

## PROCESS_PRES_PAGES_QTIME
```sql
select concat(process_name,'\:',cpu_num,',',pin) as "process-name", avg(pres_pages_qtime*( 1/delta_time)) as "pres_pages_qtime" from $table group by 1 order by 2 desc limit 10;
```

## PROCESS_READY_TIME
```sql
select concat(process_name,'\:',cpu_num,',',pin) as "process-name", avg(ready_time*((100.0/delta_time))) as "ready_time" from $table group by 1 order by 2 desc limit 10;
```

## PROCESS_SENT_RECIEVED_BYTES
```sql
select concat(process_name,'\:',cpu_num,',',pin) as "process-name", avg(sent_bytes) as "sent_bytes", avg(received_bytes) as "received_bytes" from $table group by 1 order by 2 desc limit 10;
```

## TMF_ABORTING_TRANS
```sql
select cpu_num as "tmf-name", avg(aborting_trans*(1000*1000/delta_time)) as "aborting_trans" from $table group by 1 order by 2 desc limit 10;
```

## TMF_HOME_NET_TRANS
```sql
select cpu_num as "tmf-name", avg(home_net_trans*(1000*1000/delta_time)) as "home_net_trans" from $table group by 1 order by 2 desc limit 10;
```

## TMF_HOME_NET_TRANS_ART
```sql
select cpu_num, avg(home_net_trans_qtime/home_net_trans/1000) as home_net_trans_art from  jd10k.tmf where home_net_trans<>0 group by 1 order by 2 desc
```

## TMF_HOME_NET_TRANS_QTIME
```sql
select cpu_num as "tmf-name", avg(home_net_trans_qtime*((1.0/delta_time))) as "home_net_trans_qtime" from $table group by 1 order by 2 desc limit 10;
```

## TMF_HOME_TRANS
```sql
select cpu_num as "tmf-name", avg(home_trans*(1000*1000/delta_time)) as "home_trans" from $table group by 1 order by 2 desc limit 10;
```

## TMF_HOME_TRANS_ART
```sql
select cpu_num, avg(home_trans_qtime/home_trans/1000) as home_trans_art from  $table group by 1 order by 2 desc
```

## TMF_HOME_TRANS_QTIME
```sql
select cpu_num as "tmf-name", avg(home_trans_qtime*((1/delta_time))) as "home_trans_qtime" from $table group by 1 order by 2 desc limit 10;
```

## TMF_REMOTE_TRANS
```sql
select cpu_num as "tmf-name", avg(remote_trans*(1000*1000/delta_time)) as "remote_trans" from $table group by 1 order by 2 desc limit 10;
```

## TMF_REMOTE_TRANS_QTIME
```sql
select cpu_num as "tmf-name", avg(remote_trans_qtime*( 1/delta_time)) as "remote_trans_qtime" from $table group by 1 order by 2 desc limit 10;
```

## TMF_TRANS_BACKOUT_QTIME
```sql
select cpu_num as "tmf-name", avg(trans_backout_qtime*( 1/delta_time)) as "trans_backout_qtime" from $table group by 1 order by 2 desc limit 10;
```

## TOTAL_HOME_TRANS
```sql
select cpu_num as "tmf-name", sum(home_trans) as "home_trans" from $table group by 1 order by 2 desc limit 10;
```

## Other Extracted Queries

### DISC_BY_DEVICE_TYPE
```sql
select device_type,device_subtype, sum(writes),sum(reads_) from me2.disc group by 1,2
```

### MAX_BY_SYSTEM_NAME
```sql
select system_name,concat(os_version_letter,'-',os_version_number),EXTRACT(EPOCH FROM max(to_timestamp))-EXTRACT(EPOCH FROM min(from_timestamp)) as duration,ROUND(max(delta_time/1000000),0)as interval from %measurefile%.process group by 1,2
```

### PROCESS_NSJSP_STATS
```sql
select process_name,sum(cpu_busy_time) as cpu_busy_time,100*sum(cpu_busy_time)/sum(delta_time) as nsjsp_cpu_busytime,sum(file_open_calls)as file_open_calls,sum(info_calls)as info_calls,sum(ossns_requests)as ossns_requests,sum(ossns_wait_time)as ossns_wait_time,sum(messages_sent)as messages_sent,sum(mqcs_inuse_qtime) as mqcs_inuse_qtime_NSJSP, sum(mqc_allocations) as mqc_allocationsNSJSP,sum(msgs_sent_qtime) as msgs_sent_qtimeNSJSP, sum(begin_trans) as begin_trans,sum(messages_received) as msg_rcvd,sum(recv_qtime) as recv_qtime,sum(begin_trans) as begin_trans from %measurefile%.process where process_name like '%nsjspprocessname%' group by 1 order by 1
```

### PROCESS_NSJSP_STATS
```sql
select process_name,sum(cpu_busy_time) as cpu_busy_time,100*sum(cpu_busy_time)/sum(delta_time) as nsjsp_cpu_busytime,sum(file_open_calls)as file_open_calls,sum(info_calls)as info_calls,sum(ossns_requests)as ossns_requests,sum(ossns_wait_time)as ossns_wait_time,sum(messages_sent)as messages_sent,sum(mqcs_inuse_qtime) as mqcs_inuse_qtime_NSJSP, sum(mqc_allocations) as mqc_allocationsNSJSP,sum(msgs_sent_qtime) as msgs_sent_qtimeNSJSP, sum(begin_trans) as begin_trans,sum(messages_received) as msg_rcvd,sum(recv_qtime) as recv_qtime from %measurefile%.process where process_name like '%pm_processname%' group by 1 order by 1
```

### PROCESS_NSMEF_STATS
```sql
select sum(cpu_busy_time) as nsmef_cpu_busytime,100*sum(cpu_busy_time)/sum(delta_time) as nsmef_cpu_busytime from %measurefile%.process where process_name like '%nsmefprocessname%'
```

### USERDEF_BY_CONCATPROCESS
```sql
select concat(process_name,name) as countername, sum(cast (value as int)) as userdefvalue from %measurefile%.userdef group by 1 order by 1
```

### PROCESS_NSJSP_STATS
```sql
select process_name,sum(cpu_busy_time) as cpu_busytime_ROUT,sum(messages_sent) as messages_sent_ROUT,sum(mqc_allocations) as mqc_allocationsNSJSP,sum(mqcs_inuse_qtime) as mqcs_inuse_qtime_ROUT from %measurefile%.process where process_name like %routprocessname% group by 1 order by 1
```

### FILE_NSJSP_STATS
```sql
select sum(file_busy_time) as file_busy_time,sum(messages) as messages,file_name_volume from %measurefile%.file where opener_processname like '%nsjspprocessname%' and file_name_volume like %routprocessname% group by 3 order by 3
```

### FILE_NSJSP_STATS
```sql
select %runtype% as runtype,'%measurefile%' as measurefile, concat(file_name_volume, file_name_subvol, file_name_filename) as filename, file_open_type as file_open_type,sum(file_busy_time) as file_busy_time,sum(reads_) as reads,sum(read_bytes) as read_bytes,sum(writes) as writes,sum(write_bytes) as write_bytes , sum(messages) as messages,sum(Deletes_or_Writereads_) as Deletes_or_Writereads_, sum(Updates_or_Replies) as Updates_or_Replies from %measurefile%.file where opener_processname like '%nsjspprocessname%' group by 3,4 order by 3 desc
```

### FILE_BY_RUNTYPE
```sql
select %runtype% as runtype,'%measurefile%' as measurefile,opener_processname as openerprocessname, concat(file_name_volume, file_name_subvol, file_name_filename) as filename, file_open_type as file_open_type,sum(file_busy_time) as file_busy_time,sum(reads_) as reads,sum(read_bytes) as read_bytes,sum(writes) as writes,sum(write_bytes) as write_bytes , sum(messages) as messages,sum(Deletes_or_Writereads_) as Deletes_or_Writereads_, sum(Updates_or_Replies) as Updates_or_Replies from %measurefile%.file where opener_processname like '%' group by 3,4,5 order by 4 desc
```

### TMF_BY_CPU_NUM
```sql
select tmf.cpu_num as cpu_num,sum(home_trans) as home_trans from %measurefile%.tmf group by 1 order by 1
```

### PROCESSH_BY_CONCATOBJECT_F
```sql
select concat(object_file_name_mid_pathid,'\:',object_file_name_mid_crvsn,'\:',code_range) as code_file, cast(sum(cast(code_space_busy_samples as numeric))/count(*) as numeric)as samples ,cast(sum(cast(code_range_busy_samples as numeric))/count(*) as numeric)as code_range_busy_samples , cast(sum(cast(process_busy_samples as numeric))/count(*) as numeric)as process_busy_samples, cast(sum(cast(native_busy_samples as numeric))/count(*) as numeric)as native_busy_samples from %measurefile%.processh where (cast(code_range_busy_samples as numeric) != 0) group by 1 order by 4
```

### FILE_PM_STATS
```sql
select concat(file_name_volume, file_name_subvol, file_name_filename) as filename, file_open_type as file_open_type,sum(file_busy_time) as file_busy_time,sum(reads_) as reads,sum(read_bytes) as read_bytes,sum(writes) as writes,sum(write_bytes) as write_bytes , sum(messages) as messages,sum(Deletes_or_Writereads_) as Deletes_or_Writereads_, sum(Updates_or_Replies) as Updates_or_Replies from %measurefile%.file where opener_processname like '%pm_processname%' group by 1,2 order by 3 desc
```

### SQLSTMT_BY_PROCESS_NAME
```sql
select process_name ,sum(calls) as "calls",sum(elapsed_busy_time) as "elapsed_busy_time",sum(records_used) as "records_used",sum(records_accessed) as "records_accessed",sum(messages) as "messages", sum(disc_reads_) as "disc_reads_",sum(message_bytes) as "message_bytes",sum(elapsed_recompile_time) as "elapsed_recompile_time" from %measurefile%.sqlstmt where process_name like '%sqlstmt_procname%' group by 1
```

### DISC_BY_DEVICE_NAME
```sql
select device_name, config_name, sum (read_qbusy_time) as "read_qbusy_time",sum(read_qtime) as "read_qtime",sum(write_qbusy_time)as "write_qbusy_time",sum(write_qtime)as "write_qtime",sum(device_qbusy_time) as "device_qbusy_time" from %measurefile%.disc group by 1,2 order by 7 desc
```

### UNKNOWN_BY_CPU_NUM
```sql
select cpu_num, (select avg(100*ipu_busy_time/delta_time) as ipu_0_busy_time from $schema.ipu where ipu_num\=0 and cpu_num\=c.cpu_num), (select avg(100*ipu_busy_time/delta_time) as ipu_1_busy_time from $schema.ipu where ipu_num\=1 and cpu_num\=c.cpu_num), (select avg(100*ipu_busy_time/delta_time) as ipu_2_busy_time from $schema.ipu where ipu_num\=2 and cpu_num\=c.cpu_num), (select avg(100*ipu_busy_time/delta_time) as ipu_4_busy_time from $schema.ipu where ipu_num\=3 and cpu_num\=c.cpu_num) from $schema.ipu c group by cpu_num order by cpu_num
```
