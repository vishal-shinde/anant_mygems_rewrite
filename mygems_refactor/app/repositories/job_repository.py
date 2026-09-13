from app.repositories.base_repository import BaseRepository


class JobRepository(BaseRepository):
    def get_jobs(self, limit: int = 50):
        return self.fetch_all(
            """
            SELECT job_id, job_code, customer_name, status, assigned_to
            FROM jobs
            ORDER BY job_id DESC
            LIMIT %s
            """,
            (limit,),
        )

    def save_job(self, job_code: str, customer_id: int | None, customer_name: str, job_type: str, status: str, assigned_to: str | None):
        return self.execute(
            """
            INSERT INTO jobs (job_code, customer_id, customer_name, job_type, status, assigned_to)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (job_code, customer_id, customer_name, job_type, status, assigned_to),
        )
