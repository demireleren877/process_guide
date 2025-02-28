from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from datetime import datetime
import os
from executor import ProcessExecutor
import json

app = Flask(__name__)
CORS(app)

# Gizli anahtar ayarı
app.secret_key = 'your-super-secret-key-here'  # Güvenli bir değer kullanın

# JSON filtresi ekle
@app.template_filter('from_json')
def from_json(value):
    try:
        return json.loads(value)
    except:
        return {}

@app.template_filter('format_datetime')
def format_datetime(value):
    if not value:
        return ''
    try:
        if isinstance(value, str):
            dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        else:
            dt = value
        return dt.strftime('%d.%m.%Y %H:%M')
    except:
        return value

@app.template_global()
def get_mail_replies(variable_id):
    """Mail değişkenine ait yanıtları getirir"""
    return MailReply.query.filter_by(
        variable_id=variable_id,
        is_reply=True
    ).order_by(MailReply.received_at.asc()).all()

# Instance klasörünü oluştur
os.makedirs(app.instance_path, exist_ok=True)

# Veritabanı konfigürasyonu
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'processes.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# ProcessExecutor için veritabanı yolunu ayarla
ProcessExecutor.set_db_path(os.path.join(app.instance_path, 'processes.db'))

# Veritabanı modelleri
class Process(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    is_started = db.Column(db.Boolean, default=False)
    started_at = db.Column(db.DateTime)  # Sürecin başlama tarihi
    steps = db.relationship('Step', 
                          backref='process', 
                          lazy=True, 
                          cascade='all, delete-orphan')  # Cascade silme ekle

    def get_completion_percentage(self):
        """Sürecin tamamlanma yüzdesini hesapla"""
        # Tüm adımları (alt adımlar dahil) getir
        all_steps = []
        main_steps = Step.query.filter_by(process_id=self.id, parent_id=None).all()
        
        for main_step in main_steps:
            all_steps.append(main_step)
            substeps = Step.query.filter_by(process_id=self.id).filter(Step.parent_id == main_step.id).all()
            all_steps.extend(substeps)
            # Alt adımların alt adımlarını da ekle
            for substep in substeps:
                sub_substeps = Step.query.filter_by(process_id=self.id).filter(Step.parent_id == substep.id).all()
                all_steps.extend(sub_substeps)
        
        total_steps = len(all_steps)
        if total_steps == 0:
            return 0
        
        completed_steps = sum(1 for step in all_steps if step.status == 'done')
        return int((completed_steps / total_steps) * 100)

    def get_status(self):
        """Sürecin genel durumunu belirle"""
        if not self.is_started:
            return 'not_started'
        
        # Tüm adımları (alt adımlar dahil) getir
        all_steps = []
        main_steps = Step.query.filter_by(process_id=self.id, parent_id=None).all()
        
        for main_step in main_steps:
            all_steps.append(main_step)
            substeps = Step.query.filter_by(process_id=self.id).filter(Step.parent_id == main_step.id).all()
            all_steps.extend(substeps)
            # Alt adımların alt adımlarını da ekle
            for substep in substeps:
                sub_substeps = Step.query.filter_by(process_id=self.id).filter(Step.parent_id == substep.id).all()
                all_steps.extend(sub_substeps)
        
        if not all_steps:
            return 'empty'
        
        all_done = all(step.status == 'done' for step in all_steps)
        has_in_progress = any(step.status == 'in_progress' for step in all_steps)
        has_waiting = any(step.status == 'waiting' for step in all_steps)
        
        if all_done:
            return 'done'
        elif has_in_progress:
            return 'in_progress'
        elif has_waiting:
            return 'waiting'
        else:
            return 'not_started'

class Step(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    step_number = db.Column(db.Integer)  # Süreç içindeki sıra numarası
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    type = db.Column(db.String(50))  # python_script, excel_file, sql_script
    file_path = db.Column(db.String(255))
    order = db.Column(db.Integer)
    parent_id = db.Column(db.Integer, db.ForeignKey('step.id', ondelete='CASCADE'), nullable=True)
    process_id = db.Column(db.Integer, db.ForeignKey('process.id', ondelete='CASCADE'), nullable=False)
    responsible = db.Column(db.String(100))
    status = db.Column(db.String(20), default='not_started')  # not_started, waiting, in_progress, done
    dependencies = db.relationship('StepDependency', 
                                 foreign_keys='StepDependency.step_id',
                                 backref='dependent_step', 
                                 lazy=True,
                                 cascade='all, delete-orphan')
    sub_steps = db.relationship('Step',
                              backref=db.backref('parent', remote_side=[id]),
                              lazy=True,
                              cascade='all, delete-orphan')
    variables = db.relationship('StepVariable', 
                              backref='step', 
                              lazy=True,
                              cascade='all, delete-orphan')

    def __init__(self, **kwargs):
        super(Step, self).__init__(**kwargs)
        if self.order is None:
            last_step = Step.query.filter_by(
                process_id=self.process_id,
                parent_id=self.parent_id
            ).order_by(Step.order.desc()).first()
            self.order = (last_step.order + 1) if last_step else 1

        if self.status is None:
            self.status = 'not_started'
            
        # Süreç içindeki sıra numarasını belirle
        if self.step_number is None:
            last_step = Step.query.filter_by(
                process_id=self.process_id
            ).order_by(Step.step_number.desc()).first()
            self.step_number = (last_step.step_number + 1) if last_step else 1

    def get_full_order(self):
        if not self.parent_id:
            return str(self.order)
        
        parent = self.parent
        if not parent.parent_id:
            return f"{parent.order}.{self.order}"
        else:
            return f"{parent.get_full_order()}.{self.order}"

    def get_step_id(self):
        """Süreç ID'si ve adım numarasından oluşan benzersiz ID döndürür"""
        return f"{self.process_id}_{self.step_number}"

    def update_status(self):
        if not self.sub_steps:  # Alt adımı olmayan adımlar
            return self.status
        
        # Tüm alt adımların durumlarını kontrol et
        all_not_started = all(step.status == 'not_started' for step in self.sub_steps)
        has_in_progress = any(step.status == 'in_progress' for step in self.sub_steps)
        has_waiting = any(step.status == 'waiting' for step in self.sub_steps)
        all_done = all(step.status == 'done' for step in self.sub_steps)
        
        # Durum öncelik sırası: devam ediyor > beklemede > başlamadı > tamamlandı
        if has_in_progress:
            self.status = 'in_progress'
        elif has_waiting:
            self.status = 'waiting'
        elif all_not_started:
            self.status = 'not_started'
        elif all_done:
            self.status = 'done'
        else:
            self.status = 'in_progress'  # Karışık durumda varsayılan olarak devam ediyor
        
        return self.status

class StepDependency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    step_id = db.Column(db.Integer, db.ForeignKey('step.id'), nullable=False)
    depends_on_id = db.Column(db.Integer, db.ForeignKey('step.id'), nullable=False)

class StepVariable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    step_id = db.Column(db.Integer, db.ForeignKey('step.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    var_type = db.Column(db.String(50), nullable=False)  # text, number, boolean
    default_value = db.Column(db.String(255))
    scope = db.Column(db.String(20), nullable=False, default='step_only', server_default='step_only')  # step_only, process_wide
    parent_variable_id = db.Column(db.Integer, db.ForeignKey('step_variable.id', name='fk_parent_variable', ondelete='CASCADE'), nullable=True)
    mail_status = db.Column(db.String(20), default='waiting')  # waiting, received
    
    # Alt değişkenler için ilişki
    child_variables = db.relationship('StepVariable',
                                    backref=db.backref('parent_variable', remote_side=[id]),
                                    cascade="all, delete-orphan",
                                    passive_deletes=True)

class MailReply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    variable_id = db.Column(db.Integer, db.ForeignKey('step_variable.id', ondelete='CASCADE'), nullable=False)
    subject = db.Column(db.String(255))
    sender = db.Column(db.String(255))
    received_at = db.Column(db.DateTime, default=datetime.now)
    original_subject = db.Column(db.String(255))
    is_reply = db.Column(db.Boolean, default=False)

# Ana sayfa
@app.route('/')
def index():
    processes = Process.query.all()
    return render_template('index.html', processes=processes)

# Süreç detay sayfası
@app.route('/process/<int:process_id>')
def process_detail(process_id):
    process = Process.query.get_or_404(process_id)
    
    # Ana adımları sırala
    main_steps = Step.query.filter_by(
        process_id=process_id,
        parent_id=None
    ).order_by(Step.order).all()
    
    # Tüm adımları hiyerarşik olarak düzenle
    organized_steps = []
    for main_step in main_steps:
        organized_steps.append(main_step)
        # Alt adımları recursive olarak ekle
        organized_steps.extend(get_substeps_recursive(main_step.id))
    
    return render_template('process_detail.html', process=process, steps=organized_steps)

def get_substeps_recursive(parent_id):
    """Alt adımları recursive olarak getir"""
    substeps = []
    direct_substeps = Step.query.filter_by(parent_id=parent_id).order_by(Step.order).all()
    
    for substep in direct_substeps:
        substeps.append(substep)
        # Alt adımın alt adımlarını recursive olarak getir
        substeps.extend(get_substeps_recursive(substep.id))
    
    return substeps

# Yeni süreç oluşturma
@app.route('/process/new', methods=['GET', 'POST'])
def new_process():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        if name:
            process = Process(name=name, description=description)
            db.session.add(process)
            db.session.commit()
            return redirect(url_for('process_detail', process_id=process.id))
    
    return render_template('new_process.html')

# Süreç silme
@app.route('/process/<int:process_id>/delete', methods=['POST'])
def delete_process(process_id):
    try:
        process = Process.query.get_or_404(process_id)
        
        # Tüm adımları ve alt adımları bul
        all_steps = []
        main_steps = Step.query.filter_by(process_id=process_id, parent_id=None).all()
        
        for main_step in main_steps:
            all_steps.append(main_step)
            substeps = Step.query.filter_by(process_id=process_id).filter(Step.parent_id == main_step.id).all()
            all_steps.extend(substeps)
            # Alt adımların alt adımlarını da ekle
            for substep in substeps:
                sub_substeps = Step.query.filter_by(process_id=process_id).filter(Step.parent_id == substep.id).all()
                all_steps.extend(sub_substeps)
        
        # Her adımın değişkenlerini ve bağımlılıklarını sil
        for step in all_steps:
            # Değişkenleri sil
            StepVariable.query.filter_by(step_id=step.id).delete()
            
            # Bağımlılıkları sil
            StepDependency.query.filter_by(step_id=step.id).delete()
            StepDependency.query.filter_by(depends_on_id=step.id).delete()
        
        # Süreci sil (cascade ile tüm adımlar da silinecek)
        db.session.delete(process)
        db.session.commit()
        
        flash('Süreç ve tüm ilişkili veriler başarıyla silindi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Süreç silinirken hata oluştu: {str(e)}', 'error')
    
    return redirect(url_for('index'))

# Yeni adım oluşturma
@app.route('/process/<int:process_id>/step/new', methods=['GET', 'POST'])
def new_step(process_id):
    process = Process.query.get_or_404(process_id)
    
    if process.is_started:
        flash('Başlatılmış süreçlere yeni adım eklenemez.', 'error')
        return redirect(url_for('process_detail', process_id=process_id))
    
    parent_id = request.args.get('parent_id', type=int)
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        step_type = request.form.get('type')
        file_path = request.form.get('file_path')
        responsible = request.form.get('responsible')
        
        if name and step_type:
            try:
                step = Step(
                    name=name,
                    description=description,
                    type=step_type,
                    file_path=file_path,
                    responsible=responsible,
                    parent_id=parent_id,
                    process_id=process_id
                )
                db.session.add(step)
                db.session.commit()
                
                # Debug log
                app.logger.info(f'New step created - ID: {step.id}, Type: {step_type}')
                variables = StepVariable.query.filter_by(step_id=step.id).all()
                app.logger.info(f'Variables for step {step.id}: {[{"id": v.id, "name": v.name} for v in variables]}')
                
                flash('Adım başarıyla oluşturuldu', 'success')
                return redirect(url_for('process_detail', process_id=process_id))
            except Exception as e:
                db.session.rollback()
                flash(f'Adım oluşturulurken hata oluştu: {str(e)}', 'error')
            return redirect(url_for('process_detail', process_id=process_id))
    
    # Parent step bilgisini al
    parent_step = None
    full_order = None
    if parent_id:
        parent_step = Step.query.get(parent_id)
        if parent_step:
            # Bir sonraki alt adımın sırasını belirle
            next_order = 1
            last_substep = Step.query.filter_by(parent_id=parent_id).order_by(Step.order.desc()).first()
            if last_substep:
                next_order = last_substep.order + 1
            
            # Tam sırayı oluştur
            full_order = f"{parent_step.get_full_order()}.{next_order}"
    
    return render_template('new_step.html', 
                         process=process, 
                         parent_id=parent_id, 
                         parent_step=parent_step,
                         full_order=full_order)

# Adım çalıştırma
@app.route('/step/<int:step_id>/execute', methods=['POST'])
def execute_step(step_id):
    step = Step.query.get_or_404(step_id)
    process = Process.query.get(step.process_id)
    
    # Sürecin başlatılıp başlatılmadığını kontrol et
    if not process.is_started:
        # Süreci başlat
        process.is_started = True
        db.session.commit()
        ProcessExecutor.start_process()
    
    # Mail tipi adımlar için değişkenleri işle
    if step.type == 'mail':
        mail_configs = []
        for var in step.variables:
            if var.var_type == 'mail_config':
                try:
                    config = json.loads(var.default_value) if var.default_value else None
                    if config and config.get('active', False):  # Sadece aktif olan mailleri gönder
                        # Mail gönderilme zamanını ekle
                        config['sent_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        var.default_value = json.dumps(config)
                        mail_configs.append(config)
                except:
                    continue
        
        if not mail_configs:
            return jsonify({
                'success': False,
                'error': 'Aktif mail konfigürasyonu bulunamadı.'
            })
        
        result = ProcessExecutor.execute_step(
            step_type=step.type,
            file_path=step.file_path,
            variables=mail_configs
        )
        
        # Mail gönderimi başarılı olduysa değişiklikleri kaydet
        if result['success']:
            try:
                db.session.commit()
            except:
                db.session.rollback()
        
        return jsonify(result)
    else:
        # Windows için Downloads klasörünü doğru şekilde belirle
        output_dir = os.path.join(os.environ['USERPROFILE'], 'Downloads')
        result = ProcessExecutor.execute_step(
            step_type=step.type,
            file_path=step.file_path,
            output_dir=output_dir if step.type == 'python_script' else None
        )
        
        # Script başarıyla çalıştıysa adımı tamamlandı olarak işaretle
        if result.get('success'):
            step.status = 'done'
            db.session.commit()
            
            # Eğer çıktı dosyası varsa, yolunu sonuca ekle
            if result.get('output_file'):
                output_path = os.path.join(output_dir, result['output_file'])
                result['output'] = f"Script başarıyla çalıştırıldı. Çıktı dosyası: {output_path}"
    
    return jsonify(result)

# Değişken ekleme
@app.route('/step/<int:step_id>/variables/new', methods=['GET', 'POST'])
def new_variable(step_id):
    step = Step.query.get_or_404(step_id)
    
    if step.type not in ['python_script', 'sql_script', 'mail']:
        return redirect(url_for('process_detail', process_id=step.process_id))
    
    if request.method == 'POST':
        name = request.form.get('name')
        var_type = request.form.get('var_type')
        default_value = request.form.get('default_value')
        scope = request.form.get('scope', 'step_only')
        
        # Mail tipi adımlar için sadece mail_config değişkenine izin ver
        if step.type == 'mail' and var_type != 'mail_config':
            flash('Mail tipi adımlarda sadece mail konfigürasyonu eklenebilir.', 'error')
            return redirect(url_for('new_variable', step_id=step_id))
        
        if name and var_type:
            # Eğer bu bir alt adımsa ve scope process_wide ise,
            # ana adımın değişkenlerinden birini referans almalı
            parent_variable_id = None
            if step.parent_id and scope == 'process_wide':
                parent_variable_id = request.form.get('parent_variable_id')
                if not parent_variable_id:
                    flash('Süreç genelinde değişken için ana adımdan bir değişken seçmelisiniz.', 'error')
                    return redirect(url_for('new_variable', step_id=step_id))
            
            variable = StepVariable(
                step_id=step_id,
                name=name,
                var_type=var_type,
                default_value=default_value,
                scope=scope,
                parent_variable_id=parent_variable_id,
                mail_status='waiting' if var_type == 'mail_config' else None
            )
            db.session.add(variable)
            db.session.commit()

            # Yeni mail_config değişkeni oluşturulduğunda, ilgili yanıtları temizle
            if var_type == 'mail_config':
                # Önce değişkene ait tüm yanıtları sil
                MailReply.query.filter_by(variable_id=variable.id).delete()
                db.session.commit()

            return redirect(url_for('process_detail', process_id=step.process_id))
    
    # Ana adımın değişkenlerini template'e gönder
    parent_variables = []
    if step.parent_id:
        parent_variables = StepVariable.query.filter_by(step_id=step.parent_id).all()
    
    # Mail tipi adımlar için sadece mail_config seçeneğini göster
    is_mail_step = step.type == 'mail'
    
    return render_template('new_variable.html', 
                         step=step, 
                         parent_variables=parent_variables,
                         is_mail_step=is_mail_step)

# Değişken güncelleme
@app.route('/variable/<int:variable_id>/update', methods=['POST'])
def update_variable(variable_id):
    variable = StepVariable.query.get_or_404(variable_id)
    field = request.form.get('field')
    value = request.form.get('value')
    
    if field and value is not None:
        if field == 'name':
            variable.name = value
        elif field == 'var_type':
            variable.var_type = value
        elif field == 'default_value':
            variable.default_value = value
        
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'success': False}), 400

# Değişken silme
@app.route('/variable/<int:variable_id>/delete', methods=['POST'])
def delete_variable(variable_id):
    try:
        variable = StepVariable.query.get_or_404(variable_id)
        step_id = variable.step_id
        process_id = Step.query.get(step_id).process_id
        
        # Önce alt değişkenleri sil
        StepVariable.query.filter_by(parent_variable_id=variable_id).delete()
        
        # Şimdi ana değişkeni sil
        db.session.delete(variable)
        db.session.commit()
        
        flash('Değişken başarıyla silindi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Değişken silinirken hata oluştu: {str(e)}', 'error')
    
    return redirect(url_for('process_detail', process_id=process_id))

# Adım güncelleme
@app.route('/step/<int:step_id>/update', methods=['POST'])
def update_step(step_id):
    step = Step.query.get_or_404(step_id)
    field = request.form.get('field')
    value = request.form.get('value')
    
    if field and value is not None:
        if field == 'name':
            step.name = value
        elif field == 'description':
            step.description = value
        elif field == 'file_path':
            step.file_path = value
        elif field == 'responsible':
            step.responsible = value
        
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'success': False}), 400

# Adım silme
@app.route('/step/<int:step_id>/delete', methods=['POST'])
def delete_step(step_id):
    step = Step.query.get_or_404(step_id)
    process_id = step.process_id
    parent_id = step.parent_id
    deleted_order = step.order
    
    if step.process.is_started:
        flash('Başlatılmış süreçlerden adım silinemez.', 'error')
        return redirect(url_for('process_detail', process_id=process_id))
    
    try:
        # Önce alt adımların değişkenlerini sil
        for substep in Step.query.filter_by(parent_id=step_id).all():
            StepVariable.query.filter_by(step_id=substep.id).delete()
        
        # Ana adımın değişkenlerini sil
        StepVariable.query.filter_by(step_id=step_id).delete()
        
        # Alt adımları sil
        Step.query.filter_by(parent_id=step_id).delete()
        
        # Ana adımı sil
        db.session.delete(step)
        
        # Aynı seviyedeki diğer adımların sırasını güncelle
        remaining_steps = Step.query.filter_by(
            process_id=process_id,
            parent_id=parent_id
        ).filter(Step.order > deleted_order).all()
        
        for remaining_step in remaining_steps:
            remaining_step.order -= 1
        
        db.session.commit()
        flash('Adım başarıyla silindi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Adım silinirken hata oluştu: {str(e)}', 'error')
    
    return redirect(url_for('process_detail', process_id=process_id))

# Adımları yeniden sırala
def reorder_steps(process_id, parent_id=None):
    steps = Step.query.filter_by(
        process_id=process_id,
        parent_id=parent_id
    ).order_by(Step.order).all()
    
    for index, step in enumerate(steps, start=1):
        step.order = index
        # Alt adımları da yeniden sırala
        reorder_steps(process_id, step.id)

# Süreci başlat
@app.route('/process/<int:process_id>/start', methods=['POST'])
def start_process(process_id):
    process = Process.query.get_or_404(process_id)
    process.is_started = True
    process.started_at = datetime.now()  # UTC yerine yerel saat
    
    # ProcessExecutor'ı başlat
    ProcessExecutor.start_process()
    
    steps = Step.query.filter_by(process_id=process_id, parent_id=None).all()
    for step in steps:
        if step.status == 'not_started':
            step.status = 'waiting'
    
    db.session.commit()
    return redirect(url_for('process_detail', process_id=process_id))

# Uygulama başlangıcında süreç durumunu kontrol et
def check_process_status():
    with app.app_context():
        # Veritabanında başlatılmış süreç var mı kontrol et
        started_process = Process.query.filter_by(is_started=True).first()
        if started_process:
            # Eğer başlatılmış süreç varsa ProcessExecutor'ı da başlat
            ProcessExecutor.start_process()

# Her istek öncesi süreç durumunu kontrol et
@app.before_request
def before_request():
    if not getattr(app, '_got_first_request', False):
        check_process_status()
        app._got_first_request = True

# Adım durumu güncelleme
@app.route('/step/<int:step_id>/status', methods=['POST'])
def update_step_status(step_id):
    step = Step.query.get_or_404(step_id)
    new_status = request.form.get('status')
    
    if new_status in ['not_started', 'waiting', 'in_progress', 'done']:
        # Ana adımın veya alt adımın durumu değiştirildiğinde
        # Tüm alt adımları güncelle (hem ana adım hem de alt adım için)
        update_substeps_status(step.id, new_status)
        
        # Adımın kendi durumunu güncelle
        step.status = new_status
        db.session.commit()
        
        # Alt adımın durumu değiştirildiğinde ana adımı güncelle
        if step.parent_id:
            parent = step.parent
            while parent:
                parent.update_status()
                db.session.commit()
                parent = parent.parent
    
    return redirect(url_for('process_detail', process_id=step.process_id))

def update_substeps_status(parent_id, status):
    """Alt adımların durumlarını recursive olarak güncelle"""
    substeps = Step.query.filter_by(parent_id=parent_id).all()
    for substep in substeps:
        substep.status = status
        # Alt adımın alt adımlarını da güncelle
        update_substeps_status(substep.id, status)
        db.session.commit()

# Toplu değişken güncelleme
@app.route('/variables/batch-update', methods=['POST'])
def batch_update_variables():
    try:
        step_id = request.form.get('step_id')
        step = Step.query.get_or_404(step_id)
        
        # Form verilerini işle
        for var in step.variables:
            if var.var_type == 'mail_config':
                # Mail konfigürasyonu için özel işleme
                mail_config = {
                    'to': [addr.strip() for addr in request.form.get(f'mail_to_{var.id}', '').split(',') if addr.strip()],
                    'cc': [addr.strip() for addr in request.form.get(f'mail_cc_{var.id}', '').split(',') if addr.strip()],
                    'subject': request.form.get(f'mail_subject_{var.id}', ''),
                    'body': request.form.get(f'mail_body_{var.id}', ''),
                    'active': request.form.get(f'mail_active_{var.id}') is not None
                }
                var.default_value = json.dumps(mail_config)
            elif var.var_type == 'boolean':
                var.default_value = str(request.form.get(f'variable_{var.id}') == 'true').lower()
            else:
                value = request.form.get(f'variable_{var.id}')
                if value is not None:
                    var.default_value = value
            
            # Alt değişkenleri güncelle
            for child_var in var.child_variables:
                child_var.default_value = var.default_value
        
        db.session.commit()
        flash('Değişkenler başarıyla güncellendi', 'success') 
    except Exception as e:
        db.session.rollback()
        flash(f'Değişkenler güncellenirken hata oluştu: {str(e)}', 'error')
    
    return redirect(url_for('process_detail', process_id=step.process_id))

# Mail yanıt durumu kontrolü
@app.route('/step/<int:step_id>/check-mail-replies', methods=['POST'])
def check_mail_replies(step_id):
    step = Step.query.get_or_404(step_id)
    process = step.process
    
    if step.type != 'mail':
        return jsonify({
            'success': False,
            'error': 'Bu adım mail tipi değil'
        })
    
    if not process.is_started:
        return jsonify({
            'success': False,
            'error': 'Süreç henüz başlatılmamış'
        })
    
    # Mail değişkenlerini başta al
    mail_variables = StepVariable.query.filter_by(step_id=step_id, var_type='mail_config').all()
    
    # Süreç başlama tarihini ProcessExecutor'a gönder
    result = ProcessExecutor.execute_mail_check(start_date=process.started_at)
    
    if result['success'] and result['output']:
        received_mails = result['output']
        
        all_replies_received = True
        for var in mail_variables:
            try:
                config = json.loads(var.default_value) if var.default_value else {}
                subject = config.get('subject', '')
                
                if not subject:
                    continue

                # Mevcut yanıtları kontrol et
                existing_replies = MailReply.query.filter_by(
                    variable_id=var.id,
                    is_reply=True
                ).all()

                has_reply = False
                for mail in received_mails:
                    mail_subject = mail['subject'].lower()
                    original_subject = subject.lower()
                    
                    is_reply = (
                        (mail_subject.startswith('re:') and original_subject in mail_subject) or
                        (original_subject.startswith('re:') and mail_subject.replace('re:', '').strip() in original_subject) or
                        mail_subject == original_subject
                    )
                    
                    if is_reply:
                        has_reply = True
                        # Eğer bu yanıt daha önce kaydedilmemişse kaydet
                        if not any(reply.subject == mail['subject'] for reply in existing_replies):
                            reply = MailReply(
                                variable_id=var.id,
                                subject=mail['subject'],
                                sender=mail['sender'],
                                received_at=datetime.strptime(mail['received'], '%Y-%m-%d %H:%M:%S'),
                                original_subject=subject,
                                is_reply=True
                            )
                            db.session.add(reply)
                
                if has_reply:
                    var.mail_status = 'received'
                else:
                    var.mail_status = 'waiting'
                    if subject:  # Sadece konusu olan mailler için kontrol et
                        all_replies_received = False
                
            except Exception as e:
                app.logger.error(f"Mail kontrolü sırasında hata: {str(e)}")
                continue
        
        db.session.commit()
        
        if all_replies_received:
            step.status = 'done'
            db.session.commit()
    
    # Yanıt durumunu JSON olarak döndür
    response_data = {
        'success': True,
        'output': result.get('output', []),
        'mail_statuses': []
    }
    
    # Her mail değişkeni için durum bilgisini ekle
    for var in mail_variables:
        try:
            config = json.loads(var.default_value) if var.default_value else {}
            replies = MailReply.query.filter_by(variable_id=var.id, is_reply=True).all()
            
            status_data = {
                'variable_id': var.id,
                'subject': config.get('subject', ''),
                'status': var.mail_status,
                'replies': [{
                    'subject': reply.subject,
                    'sender': reply.sender,
                    'received_at': reply.received_at.strftime('%Y-%m-%d %H:%M:%S')
                } for reply in replies]
            }
            response_data['mail_statuses'].append(status_data)
        except:
            continue
    
    return jsonify(response_data)

# Süreci durdur
@app.route('/process/<int:process_id>/stop', methods=['POST'])
def stop_process(process_id):
    process = Process.query.get_or_404(process_id)
    process.is_started = False
    
    # ProcessExecutor'ı durdur
    ProcessExecutor.stop_process()
    
    db.session.commit()
    return redirect(url_for('process_detail', process_id=process_id))

# Mail konfigürasyonunu sil
@app.route('/step/<int:step_id>/mail-config/<int:var_id>/delete', methods=['POST'])
def delete_mail_config(step_id, var_id):
    try:
        step = Step.query.get_or_404(step_id)
        variable = StepVariable.query.get_or_404(var_id)
        
        if variable.step_id != step_id:
            error_msg = f"Variable {var_id} does not belong to step {step_id}"
            flash(error_msg, 'error')
            return redirect(url_for('process_detail', process_id=step.process_id))
        
        db.session.delete(variable)
        db.session.commit()
        flash('Mail konfigürasyonu başarıyla silindi', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Mail konfigürasyonu silinirken hata oluştu: {str(e)}', 'error')
    
    return redirect(url_for('process_detail', process_id=step.process_id))

# Veritabanını JSON olarak döndür
@app.route('/api/db', methods=['GET'])
def get_db_as_json():
    processes = Process.query.all()
    result = []
    
    for process in processes:
        process_data = {
            'id': process.id,
            'name': process.name,
            'description': process.description,
            'created_at': process.created_at.isoformat(),
            'is_started': process.is_started,
            'started_at': process.started_at.isoformat() if process.started_at else None,
            'completion_percentage': process.get_completion_percentage(),
            'status': process.get_status(),
            'steps': []
        }
        
        # Ana adımları al
        main_steps = Step.query.filter_by(process_id=process.id, parent_id=None).order_by(Step.order).all()
        for step in main_steps:
            step_data = get_step_data_recursive(step)
            process_data['steps'].append(step_data)
        
        result.append(process_data)
    
    return jsonify(result)

def get_step_data_recursive(step):
    """Adım verilerini alt adımlarıyla birlikte recursive olarak al"""
    step_data = {
        'id': step.id,
        'name': step.name,
        'description': step.description,
        'type': step.type,
        'file_path': step.file_path,
        'order': step.order,
        'responsible': step.responsible,
        'status': step.status,
        'variables': [],
        'sub_steps': []
    }
    
    # Değişkenleri ekle
    for var in step.variables:
        var_data = {
            'id': var.id,
            'name': var.name,
            'var_type': var.var_type,
            'default_value': var.default_value,
            'scope': var.scope,
            'mail_status': var.mail_status if var.var_type == 'mail_config' else None,
            'parent_variable_id': var.parent_variable_id,
            'mail_replies': []
        }

        # Mail yanıtlarını ekle
        if var.var_type == 'mail_config':
            replies = MailReply.query.filter_by(
                variable_id=var.id,
                is_reply=True
            ).order_by(MailReply.received_at.asc()).all()
            
            var_data['mail_replies'] = [{
                'id': reply.id,
                'subject': reply.subject,
                'sender': reply.sender,
                'received_at': reply.received_at.isoformat(),
                'original_subject': reply.original_subject
            } for reply in replies]

            # Mail konfigürasyonunu parse et
            try:
                config = json.loads(var.default_value) if var.default_value else {}
                var_data['mail_config'] = {
                    'to': config.get('to', []),
                    'cc': config.get('cc', []),
                    'subject': config.get('subject', ''),
                    'body': config.get('body', ''),
                    'active': config.get('active', False)
                }
            except:
                var_data['mail_config'] = None

        step_data['variables'].append(var_data)
    
    # Alt adımları recursive olarak ekle
    for sub_step in step.sub_steps:
        sub_step_data = get_step_data_recursive(sub_step)
        step_data['sub_steps'].append(sub_step_data)
    
    return step_data

@app.route('/debug/step/<int:step_id>/variables')
def debug_step_variables(step_id):
    step = Step.query.get_or_404(step_id)
    variables = StepVariable.query.filter_by(step_id=step_id).all()
    result = []
    for var in variables:
        result.append({
            'id': var.id,
            'name': var.name,
            'var_type': var.var_type,
            'default_value': var.default_value,
            'scope': var.scope,
            'parent_variable_id': var.parent_variable_id
        })
    return jsonify(result)

# Süreç kopyalama
@app.route('/process/<int:process_id>/copy', methods=['POST'])
def copy_process(process_id):
    try:
        # Orijinal süreci al
        original_process = Process.query.get_or_404(process_id)
        
        # Yeni süreç oluştur
        new_process = Process(
            name=f"{original_process.name} (Kopya)",
            description=original_process.description,
            is_started=False,
            started_at=None
        )
        db.session.add(new_process)
        db.session.flush()  # Yeni sürecin ID'sini al
        
        # Adım ID'lerinin eşleşmesini tutmak için sözlük
        step_id_map = {}
        
        # Ana adımları kopyala
        main_steps = Step.query.filter_by(process_id=process_id, parent_id=None).order_by(Step.order).all()
        for main_step in main_steps:
            new_main_step = copy_step(main_step, new_process.id, None)
            step_id_map[main_step.id] = new_main_step.id
            
            # Alt adımları recursive olarak kopyala
            copy_substeps_recursive(main_step.id, new_main_step.id, new_process.id, step_id_map)
        
        db.session.commit()
        flash('Süreç başarıyla kopyalandı', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Süreç kopyalanırken hata oluştu: {str(e)}', 'error')
    
    return redirect(url_for('index'))

def copy_step(original_step, new_process_id, new_parent_id):
    """Adımı ve değişkenlerini kopyalar"""
    # Yeni adım oluştur
    new_step = Step(
        name=original_step.name,
        description=original_step.description,
        type=original_step.type,
        file_path=original_step.file_path,
        order=original_step.order,
        parent_id=new_parent_id,
        process_id=new_process_id,
        responsible=original_step.responsible,
        status='not_started'
    )
    db.session.add(new_step)
    db.session.flush()  # Yeni adımın ID'sini al
    
    # Değişkenleri kopyala
    for var in original_step.variables:
        new_var = StepVariable(
            step_id=new_step.id,
            name=var.name,
            var_type=var.var_type,
            default_value=var.default_value,
            scope=var.scope,
            mail_status='waiting' if var.var_type == 'mail_config' else None
        )
        db.session.add(new_var)
    
    return new_step

def copy_substeps_recursive(original_parent_id, new_parent_id, new_process_id, step_id_map):
    """Alt adımları recursive olarak kopyalar"""
    substeps = Step.query.filter_by(parent_id=original_parent_id).order_by(Step.order).all()
    
    for substep in substeps:
        new_substep = copy_step(substep, new_process_id, new_parent_id)
        step_id_map[substep.id] = new_substep.id
        
        # Alt adımın alt adımlarını kopyala
        copy_substeps_recursive(substep.id, new_substep.id, new_process_id, step_id_map)

# Süreç güncelleme
@app.route('/process/<int:process_id>/update', methods=['POST'])
def update_process(process_id):
    try:
        process = Process.query.get_or_404(process_id)
        field = request.form.get('field')
        value = request.form.get('value')
        
        if field == 'name':
            process.name = value
        elif field == 'description':
            process.description = value
            
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Tabloları oluştur (eğer yoksa)
    app.run(debug=True, port=5001) 