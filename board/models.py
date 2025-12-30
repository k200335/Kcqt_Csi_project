# board/models.py
from django.db import models

class OuterreceiptNew(models.Model):
    idx = models.AutoField(primary_key=True)
    receiptcode = models.CharField(db_column='receiptCode', max_length=10, blank=True, null=True)
    rqcode = models.CharField(db_column='rqCode', max_length=14, blank=True, null=True)
    accode = models.CharField(db_column='acCode', max_length=14, blank=True, null=True)
    
    # --- [CSI에서 긁어온 데이터를 저장할 칸 추가] ---
    rq_no = models.CharField(max_length=50, blank=True, null=True)      # 의뢰번호
    receipt_no = models.CharField(max_length=50, blank=True, null=True)      # 접수번호
    receipt_date = models.CharField(max_length=50, blank=True, null=True)    # 접수일시
    current_status = models.CharField(max_length=50, blank=True, null=True)  # 최종진행상태
    project_name = models.TextField(blank=True, null=True)                  # 공사명
    client_name = models.CharField(max_length=100, blank=True, null=True)    # 의뢰기관
    picker_name = models.CharField(max_length=50, blank=True, null=True)     # 채취자 성명
    seal_name = models.TextField(blank=True, null=True)     # 봉인명
    # seal_name = models.CharField(max_length=50, blank=True, null=True)       # 봉인자 성명
    
    

    class Meta:
        managed = False  # 기존 DB를 사용하는 경우 False 유지
        db_table = 'OuterReceipt'