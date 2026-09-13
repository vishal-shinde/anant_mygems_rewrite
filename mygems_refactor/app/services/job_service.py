from app.repositories.job_repository import JobRepository


class JobService:
    def __init__(self, repo: JobRepository | None = None):
        self.repo = repo or JobRepository()

    def get_jobs(self, limit: int = 50):
        try:
            return self.repo.get_jobs(limit)
        except Exception:
            return []

    def create_job(self, job_code: str, customer_id: int | None, customer_name: str, job_type: str, status: str = "OPEN", assigned_to: str | None = None):
        if not job_code or not job_code.strip():
            raise ValueError("Job code is required.")
        if not customer_name or not customer_name.strip():
            raise ValueError("Customer name is required.")
        return self.repo.save_job(job_code.strip(), customer_id, customer_name.strip(), job_type.strip() if job_type else "General", status, assigned_to.strip() if assigned_to else None)
