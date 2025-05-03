# Süreç Rehberi Uygulaması - Fonksiyon Dokümantasyonu

## İçindekiler
1. [Şablon Filtreleri ve Genel Fonksiyonlar](#şablon-filtreleri-ve-genel-fonksiyonlar)
2. [Veritabanı Modelleri](#veritabanı-modelleri)
3. [Rota İşleyicileri](#rota-işleyicileri)
4. [Yardımcı Fonksiyonlar](#yardımcı-fonksiyonlar)

## Şablon Filtreleri ve Genel Fonksiyonlar

### from_json
```python
@app.template_filter('from_json')
def from_json(value):
```
**Açıklama**: JSON string'i Python sözlüğüne dönüştüren bir şablon filtresi.

**Önyüz Kullanımı**:
- process_detail.html'de adım değişkenlerindeki JSON verilerini ayrıştırmak için kullanılır
- Mail yapılandırma formlarında JSON verilerini işlemek için kullanılır

### format_datetime
```python
@app.template_filter('format_datetime')
def format_datetime(value):
```
**Açıklama**: Tarih-saat değerini belirli bir string formatına dönüştürür.

**Önyüz Kullanımı**:
- process_detail.html'de zaman damgalarını kullanıcı dostu formatta göstermek için kullanılır
- Mail yanıt listelerinde alınma tarihlerini biçimlendirmek için kullanılır

### get_mail_replies
```python
@app.template_global()
def get_mail_replies(variable_id):
```
**Açıklama**: Belirli bir değişken ID'si için tüm mail yanıtlarını getirir.

**Önyüz Kullanımı**:
- process_detail.html'de her adım için mail yanıtlarını göstermek için kullanılır
- Mail durum göstergelerinde yanıt geçmişini göstermek için kullanılır

## Veritabanı Modelleri

### Process
**Açıklama**: Sistemdeki bir süreci temsil eder.

**Önyüz Kullanımı**:
- index.html'de tüm süreçleri listelemek için kullanılır
- process_detail.html'de süreç bilgilerini göstermek için kullanılır
- Süreç durum göstergeleri ve ilerleme çubuklarında kullanılır

### Step
**Açıklama**: Bir süreçteki bir adımı temsil eder.

**Önyüz Kullanımı**:
- process_detail.html'de adım hiyerarşisini göstermek için kullanılır
- Adım çalıştırma formları ve durum göstergelerinde kullanılır
- Adım bağımlılıkları görselleştirmesinde kullanılır

## Rota İşleyicileri

### Ana Sayfa Rotası

#### index
```python
@app.route('/')
def index():
```
**Açıklama**: Tüm süreçlerle birlikte ana sayfayı görüntüler.

**Önyüz Kullanımı**:
- Uygulamanın ana giriş noktası
- Durum göstergeleriyle birlikte süreç listesini gösterir
- Süreç detaylarına ve yönetimine bağlantılar sağlar

### Süreç Yönetimi Rotası

#### new_process
```python
@app.route('/process/new', methods=['GET', 'POST'])
def new_process():
```
**Açıklama**: Yeni bir süreç oluşturur.

**Önyüz Kullanımı**:
- new_process.html formunda kullanılır
- Kullanıcı arayüzünden süreç oluşturmayı yönetir
- Süreç verilerini doğrular ve kaydeder

#### execute_step
```python
@app.route('/step/<int:step_id>/execute', methods=['POST'])
def execute_step(step_id):
```
**Açıklama**: Belirli bir adımı çalıştırır.

**Önyüz Kullanımı**:
- Adım çalıştırma düğmelerinde kullanılır
- Kullanıcı arayüzünden adım çalıştırmayı yönetir
- Adım durumunu ve ilerleme göstergelerini günceller

### Mail Yönetimi Rotası

#### check_mail_replies
```python
@app.route('/step/<int:step_id>/check-mail-replies', methods=['POST'])
def check_mail_replies(step_id):
```
**Açıklama**: Bir adım için yeni mail yanıtlarını kontrol eder.

**Önyüz Kullanımı**:
- Mail durum kontrol düğmelerinde kullanılır
- Mail durum göstergelerini günceller
- Yeni yanıtları kullanıcı arayüzünde gösterir

## Yardımcı Fonksiyonlar

### get_substeps_recursive
```python
def get_substeps_recursive(parent_id):
```
**Açıklama**: Bir üst adımın tüm alt adımlarını özyinelemeli olarak getirir.

**Önyüz Kullanımı**:
- process_detail.html'de adım hiyerarşisini oluşturmak için kullanılır
- İç içe adım yapısını göstermeye yardımcı olur

### reorder_steps
```python
def reorder_steps(process_id, parent_id=None):
```
**Açıklama**: Bir süreçteki adımları yeniden sıralar.

**Önyüz Kullanımı**:
- Adım silme veya yeniden sıralama işlemlerinden sonra kullanılır
- Kullanıcı arayüzünde doğru adım sıralamasını korur

### check_process_status
```python
def check_process_status():
```
**Açıklama**: Tüm süreçlerin durumunu kontrol eder.

**Önyüz Kullanımı**:
- Her istekten önce otomatik olarak çalışır
- Süreç durum göstergelerini günceller

### before_request
```python
@app.before_request
def before_request():
```
**Açıklama**: Her istekten önce süreç durumunu kontrol etmek için çalışır.

**Önyüz Kullanımı**:
- Süreç durumunun güncel olduğundan emin olur
- Kullanıcı arayüzü öğelerini otomatik olarak günceller

### update_substeps_status
```python
def update_substeps_status(parent_id, status):
```
**Açıklama**: Tüm alt adımların durumunu günceller.

**Önyüz Kullanımı**:
- Adım durum güncellemelerinde kullanılır
- Kullanıcı arayüzündeki durum göstergelerini günceller
- Adım hiyerarşisinde tutarlılığı korur

### get_step_data_recursive
```python
def get_step_data_recursive(step):
```
**Açıklama**: Bir adım ve alt adımları için verileri özyinelemeli olarak getirir.

**Önyüz Kullanımı**:
- API endpoint'lerinde adım verilerini sağlamak için kullanılır
- Kullanıcı arayüzünde adım hiyerarşisini oluşturmaya yardımcı olur

### copy_step
```python
def copy_step(original_step, new_process_id, new_parent_id):
```
**Açıklama**: Bir adımın kopyasını oluşturur.

**Önyüz Kullanımı**:
- Süreç kopyalama işlevselliğinde kullanılır
- Süreç adımlarını çoğaltmaya yardımcı olur

### copy_substeps_recursive
```python
def copy_substeps_recursive(original_parent_id, new_parent_id, new_process_id, step_id_map):
```
**Açıklama**: Alt adımları özyinelemeli olarak kopyalar.

**Önyüz Kullanımı**:
- Süreç kopyalama işleminde adım hiyerarşisini korumak için kullanılır
- İç içe adımların doğru şekilde kopyalanmasını sağlar

### delete_process
```python
@app.route('/process/<int:process_id>/delete', methods=['POST'])
def delete_process(process_id):
```
**Açıklama**: Bir süreci ve ilişkili verilerini siler.

**Önyüz Kullanımı**:
- Süreç silme düğmelerinde kullanılır
- Süreci kullanıcı arayüzünden kaldırır
- Süreç listesini günceller

### new_variable
```python
@app.route('/step/<int:step_id>/variables/new', methods=['GET', 'POST'])
def new_variable(step_id):
```
**Açıklama**: Bir adım için yeni bir değişken oluşturur.

**Önyüz Kullanımı**:
- Değişken oluşturma formlarında kullanılır
- Değişken tipine özel formları yönetir
- Adım değişken listesini günceller

### update_variable
```python
@app.route('/variable/<int:variable_id>/update', methods=['POST'])
def update_variable(variable_id):
```
**Açıklama**: Değişken detaylarını günceller.

**Önyüz Kullanımı**:
- Değişken düzenleme formlarında kullanılır
- Değişken değerlerini gerçek zamanlı olarak günceller
- Farklı değişken tiplerini yönetir

### delete_variable
```python
@app.route('/variable/<int:variable_id>/delete', methods=['POST'])
def delete_variable(variable_id):
```
**Açıklama**: Bir değişkeni siler.

**Önyüz Kullanımı**:
- Değişken silme düğmelerinde kullanılır
- Değişkeni kullanıcı arayüzünden kaldırır
- Değişken listesini günceller

### batch_update_variables
```python
@app.route('/variables/batch-update', methods=['POST'])
def batch_update_variables():
```
**Açıklama**: Birden fazla değişkeni aynı anda günceller.

**Önyüz Kullanımı**:
- Toplu değişken güncellemelerinde kullanılır
- Birden fazla değişken tipini yönetir
- Kullanıcı arayüzü öğelerini verimli bir şekilde günceller

### delete_mail_config
```python
@app.route('/step/<int:step_id>/mail-config/<int:var_id>/delete', methods=['POST'])
def delete_mail_config(step_id, var_id):
```
**Açıklama**: Bir mail yapılandırmasını siler.

**Önyüz Kullanımı**:
- Mail yapılandırma silme işlemlerinde kullanılır
- Mail ayarlarını kullanıcı arayüzünden kaldırır
- Mail durum göstergelerini günceller

### get_db_as_json
```python
@app.route('/api/db', methods=['GET'])
def get_db_as_json():
```
**Açıklama**: Veritabanı içeriğini JSON olarak döndürür.

**Önyüz Kullanımı**:
- Veri dışa aktarma işlevselliğinde kullanılır
- Harici sistemler için veri sağlar
- Yedekleme işlemlerinde kullanılır

### debug_step_variables
```python
@app.route('/debug/step/<int:step_id>/variables')
def debug_step_variables(step_id):
```
**Açıklama**: Adım değişkenleri için hata ayıklama endpoint'i.

**Önyüz Kullanımı**:
- Geliştirme ortamında kullanılır
- Değişken sorunlarını gidermeye yardımcı olur
- Detaylı değişken bilgisi sağlar 