from django.db import models

# ==========================================================
# 1. MS SQL 전용 모델 (조회 전용 - OuterReceipt 테이블)
# ==========================================================
class OuterreceiptNew(models.Model):
    """
    MS SQL 서버의 데이터를 읽어오기 위한 모델입니다.
    기존 시스템의 데이터를 참조하는 용도로 사용됩니다.
    """
    idx           = models.AutoField(primary_key=True)
    receiptcode   = models.CharField(db_column='receiptCode', max_length=10, blank=True, null=True)
    rqcode        = models.CharField(db_column='rqCode', max_length=14, blank=True, null=True)
    accode        = models.CharField(db_column='acCode', max_length=14, blank=True, null=True)
    
    # CSI 데이터 수집용 필드
    rq_no         = models.CharField(max_length=50, blank=True, null=True)       # 의뢰번호
    receipt_no    = models.CharField(max_length=50, blank=True, null=True)       # 접수번호
    receipt_date  = models.CharField(max_length=50, blank=True, null=True)       # 접수일시
    current_status= models.CharField(max_length=50, blank=True, null=True)       # 최종진행상태
    project_name  = models.TextField(blank=True, null=True)                      # 공사명
    client_name   = models.CharField(max_length=100, blank=True, null=True)      # 의뢰기관
    picker_name   = models.CharField(max_length=50, blank=True, null=True)       # 채취자 성명
    seal_name     = models.TextField(blank=True, null=True)                      # 봉인명
    specific_user = models.CharField(max_length=50, blank=True, null=True)       # 처리자

    class Meta:
        managed = False          # Django가 테이블을 생성/수정하지 않음 (기존 DB 사용)
        db_table = 'OuterReceipt' # MS SQL 내 실제 테이블 이름

    def __str__(self):
        return f"[{self.rqcode}] {self.project_name or 'No Project'}"


# ==========================================================
# 2. MySQL 전용 모델 (조회 및 저장용 - csi_receipts 테이블)
# ==========================================================
class CsiReceipt(models.Model):
    """
    MySQL 서버에 데이터를 저장하고 배정 현황을 관리하는 모델입니다.
    """
    id           = models.AutoField(primary_key=True)
    u_id         = models.CharField(max_length=45, db_column='의뢰번호')
    receipt_id   = models.CharField(max_length=45, db_column='접수번호', null=True, blank=True)
    receipt_date = models.CharField(max_length=45, db_column='접수일시', null=True, blank=True)
    status       = models.CharField(max_length=45, db_column='진행상태')
    project      = models.CharField(max_length=100, db_column='사업명')
    client       = models.CharField(max_length=100, db_column='의뢰기관명')
    sampler      = models.CharField(max_length=45, db_column='채취자', null=True, blank=True)
    seal         = models.CharField(max_length=100, db_column='봉인명', null=True, blank=True)
    processor    = models.CharField(max_length=45, db_column='처리자', null=True, blank=True)
    sales_type   = models.CharField(max_length=45, db_column='영업구분')
    manager      = models.CharField(max_length=45, db_column='담당자', null=True, blank=True)
    confirm      = models.CharField(max_length=45, db_column='확인', null=True, blank=True)
    amount       = models.CharField(max_length=100, db_column='시료량', null=True, blank=True)
    category     = models.CharField(max_length=45, db_column='구분')
    site_manager = models.CharField(max_length=100, db_column='현장담당자', null=True, blank=True)
    assign_date  = models.CharField(max_length=45, db_column='배정일자', null=True, blank=True)
    assign_status= models.CharField(max_length=45, db_column='배정현황', null=True, blank=True)
    unapproved   = models.CharField(max_length=45, db_column='미인정', null=True, blank=True)

    class Meta:
        managed = False          # 이미 직접 테이블을 생성했으므로 False 유지
        db_table = 'csi_receipts' # MySQL 내 실제 테이블 이름

    def __str__(self):
        return self.project