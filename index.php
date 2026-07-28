<?php
// ===== معالجة طلبات API =====
if ($_SERVER['REQUEST_URI'] === '/api/pay') {
    header('Content-Type: application/json');
    header('Access-Control-Allow-Origin: *');
    header('Access-Control-Allow-Methods: POST');
    header('Access-Control-Allow-Headers: Content-Type');

    $input = json_decode(file_get_contents('php://input'), true);

    // محاكاة نجاح الدفع (سنربطها مع Stripe لاحقاً)
    echo json_encode([
        'status' => 'success',
        'message' => 'تم الدفع بنجاح (محاكاة)',
        'amount' => $input['amount'] ?? 0
    ]);
    exit;
}

// ===== عرض الواجهة =====
?>
<!DOCTYPE html>
<html lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>بوابة الدفع</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .card {
            background: white;
            border-radius: 20px;
            padding: 40px;
            max-width: 450px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            color: #333;
            text-align: center;
            font-size: 28px;
            margin-bottom: 10px;
        }
        .subtitle {
            text-align: center;
            color: #777;
            margin-bottom: 30px;
        }
        .status {
            background: #e8f5e9;
            color: #2e7d32;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 20px;
            font-weight: bold;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            color: #555;
            margin-bottom: 5px;
            font-weight: 600;
        }
        input {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            transition: border-color 0.3s;
            box-sizing: border-box;
        }
        input:focus {
            border-color: #667eea;
            outline: none;
        }
        .btn {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
        }
        .btn:active {
            transform: translateY(0);
        }
        .result {
            margin-top: 20px;
            padding: 15px;
            border-radius: 10px;
            display: none;
        }
        .result.success {
            display: block;
            background: #e8f5e9;
            color: #2e7d32;
            border: 1px solid #a5d6a7;
        }
        .result.error {
            display: block;
            background: #ffebee;
            color: #c62828;
            border: 1px solid #ef9a9a;
        }
        .result.loading {
            display: block;
            background: #fff3e0;
            color: #e65100;
            border: 1px solid #ffcc80;
        }
        .footer {
            text-align: center;
            margin-top: 20px;
            color: #aaa;
            font-size: 12px;
        }
        .env-status {
            font-size: 12px;
            color: #888;
            margin-top: 5px;
            text-align: center;
        }
    </style>
</head>
<body>

<div class="card">
    <h1>💳 بوابة الدفع</h1>
    <p class="subtitle">ادفع بأمان عبر Stripe</p>

    <div class="status">
        ✅ الخادم يعمل بنجاح
    </div>

    <form id="paymentForm">
        <div class="form-group">
            <label>💰 المبلغ (بالدولار)</label>
            <input type="number" id="amount" value="10" step="0.01" min="1" required>
        </div>

        <div class="form-group">
            <label>💳 رقم البطاقة (للاختبار)</label>
            <input type="text" id="card" value="4242 4242 4242 4242" placeholder="4242 4242 4242 4242" required>
        </div>

        <div class="form-group">
            <label>📅 تاريخ الانتهاء (MM/YY)</label>
            <input type="text" id="expiry" value="12/26" placeholder="MM/YY" required>
        </div>

        <div class="form-group">
            <label>🔐 CVC</label>
            <input type="text" id="cvc" value="123" placeholder="123" required>
        </div>

        <button type="submit" class="btn" id="payBtn">💳 إتمام الدفع</button>
    </form>

    <div id="result" class="result"></div>

    <div class="footer">
        🌟 بيئة الاختبار | Stripe Test Mode
    </div>
    <div class="env-status">
        🔑 Stripe Key: <?php echo getenv('STRIPE_SECRET_KEY') ? '✅ موجود' : '❌ غير موجود'; ?>
    </div>
</div>

<script>
document.getElementById('paymentForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const resultDiv = document.getElementById('result');
    const payBtn = document.getElementById('payBtn');
    
    // إعادة تعيين النتيجة
    resultDiv.className = 'result';
    resultDiv.style.display = 'none';
    resultDiv.textContent = '';

    const amount = document.getElementById('amount').value;

    // عرض حالة التحميل
    resultDiv.className = 'result loading';
    resultDiv.style.display = 'block';
    resultDiv.textContent = '⏳ جاري معالجة الدفع...';
    payBtn.disabled = true;
    payBtn.textContent = '⏳ جاري...';

    try {
        const response = await fetch('/api/pay', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                amount: parseFloat(amount) * 100,
                card: document.getElementById('card').value.replace(/\s/g, ''),
                expiry: document.getElementById('expiry').value,
                cvc: document.getElementById('cvc').value
            })
        });

        const data = await response.json();

        if (data.status === 'success') {
            resultDiv.className = 'result success';
            resultDiv.textContent = '✅ ' + (data.message || 'تم الدفع بنجاح!');
        } else {
            resultDiv.className = 'result error';
            resultDiv.textContent = '❌ فشل الدفع: ' + (data.message || 'خطأ غير معروف');
        }
    } catch (error) {
        resultDiv.className = 'result error';
        resultDiv.textContent = '❌ خطأ في الاتصال بالخادم: ' + error.message;
    } finally {
        payBtn.disabled = false;
        payBtn.textContent = '💳 إتمام الدفع';
    }
});
</script>

</body>
</html>
