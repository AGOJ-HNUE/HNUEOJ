import re
from django import forms
from .models import ICPCRegistration


class ICPCRegistrationForm(forms.ModelForm):
    class Meta:
        model = ICPCRegistration
        fields = [
            'full_name',
            'student_id',
            'academic_class',
            'cohort',
            'email',
            'phone',
            'facebook_url',
            'programming_experience',
            'achievements',
            'reason',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nhập họ và tên đầy đủ',
                'required': True,
            }),
            'student_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ví dụ: 725105001',
                'required': True,
            }),
            'academic_class': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ví dụ: A1, A2, E1, ...',
                'required': True,
            }),
            'cohort': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ví dụ: K75',
                'required': True,
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'stu725105088@hnue.edu.vn',
                'required': True,
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Số điện thoại sử dụng Zalo',
                'required': True,
            }),
            'facebook_url': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://facebook.com/username (nếu có)',
            }),
            'programming_experience': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'achievements': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Liệt kê các thành tích, môn học lập trình đã học, hoặc giải thưởng đã đạt được (nếu có)...',
            }),
            'reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Nêu rõ lý do muốn tham gia tiểu ban ICPC và mục tiêu bạn muốn đạt được...',
                'required': True,
            }),
        }

    def clean_student_id(self):
        student_id = self.cleaned_data.get('student_id', '').strip()
        if not student_id:
            raise forms.ValidationError('Vui lòng nhập mã sinh viên.')
        
        # Kiểm tra trùng mã sinh viên đang chờ duyệt hoặc đã duyệt
        existing = ICPCRegistration.objects.filter(
            student_id__iexact=student_id,
            status__in=[ICPCRegistration.STATUS_PENDING, ICPCRegistration.STATUS_APPROVED]
        )
        if self.instance and self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        
        if existing.exists():
            raise forms.ValidationError('Mã sinh viên này đã có đơn đăng ký trên hệ thống!')
        
        return student_id

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise forms.ValidationError('Vui lòng nhập địa chỉ email.')

        # Kiểm tra định dạng email sinh viên HNUE: stu<mã sinh viên 9 chữ số>@hnue.edu.vn hoặc tên miền @hnue.edu.vn
        if not re.match(r'^stu\d{9}@hnue\.edu\.vn$', email, re.IGNORECASE) and not email.endswith('@hnue.edu.vn'):
            raise forms.ValidationError(
                'Email sinh viên phải là email HNUE có định dạng stu<mã sinh viên 9 chữ số>@hnue.edu.vn (Ví dụ: stu725105088@hnue.edu.vn).'
            )

        # Kiểm tra trùng email đang chờ duyệt hoặc đã duyệt
        existing = ICPCRegistration.objects.filter(
            email__iexact=email,
            status__in=[ICPCRegistration.STATUS_PENDING, ICPCRegistration.STATUS_APPROVED]
        )
        if self.instance and self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise forms.ValidationError('Địa chỉ email sinh viên này đã được sử dụng để đăng ký trên hệ thống!')

        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        # Loại bỏ khoảng trắng và ký tự đặc biệt không phải số/dấu cộng
        cleaned_phone = re.sub(r'[^\d+]', '', phone)
        if len(cleaned_phone) < 8 or len(cleaned_phone) > 15:
            raise forms.ValidationError('Số điện thoại không hợp lệ.')
        return phone
