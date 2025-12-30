from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from board.views import receipt_list
from board import views

# 1. 회원가입 로직
def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'{username}님, 가입 완료되었습니다.')
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'signup.html', {'form': form})

# 2. CSI 접수 팝업창 로직 (is_popup 변수 전달)
def csi_receipt_view(request):
    return render(request, 'csi_receipt.html', {'is_popup': True})

# 3. URL 경로 설정
urlpatterns = [
    # 메인 페이지 및 관리자
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    path('admin/', admin.site.urls),

    # 인증 관련 (로그인/로그아웃/회원가입)
    path('login/', auth_views.LoginView.as_view(template_name='index.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'), 
    path('signup/', signup, name='signup'),

    # 게시판 및 접수 현황
    # path('board/', receipt_list, name='board'),

    # [핵심 수정] CSI_접수 팝업 경로 추가 (404 에러 해결)
    path('board/csi_receipt/', csi_receipt_view, name='csi_receipt'),

    path('fetch-csi/', views.fetch_csi_data, name='fetch_csi_data'),
]
