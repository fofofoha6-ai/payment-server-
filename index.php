<?php
require 'vendor/autoload.php';

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

\Stripe\Stripe::setApiKey('sk_test_ضع_مفتاحك_السري_هنا');

$input = json_decode(file_get_contents('php://input'), true);
$amount = $input['amount'] ?? 1000;

$intent = \Stripe\PaymentIntent::create([
    'amount' => $amount,
    'currency' => 'usd',
]);

echo json_encode(['clientSecret' => $intent->client_secret]);