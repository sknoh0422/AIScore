from app.orchestration.job import Job, JobStatus

def test_job_starts_queued():
    j = Job(id="abc")
    assert j.status == JobStatus.QUEUED

def test_fail_records_stage_and_reason():
    j = Job(id="abc")
    j.fail(JobStatus.OMR, "oemer crash")
    assert j.status == JobStatus.FAILED
    assert j.failed_stage == JobStatus.OMR
    assert "oemer" in j.error
