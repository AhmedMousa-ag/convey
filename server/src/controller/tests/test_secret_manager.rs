use crate::controller::secret_manager::generate_secret_key;

#[tokio::test(flavor = "multi_thread", worker_threads = 10)]
pub async fn test_secret_manager() {
    let hashed_metadata = "test_metadata";
    let secret = generate_secret_key(hashed_metadata).await;

    assert_eq!(secret.len(), 64); // Hashed secret key should be 64 characters long (SHA-256 hash in hex)
    // Assert if it's a valid hexadecimal string
    assert!(secret.chars().all(|c| c.is_digit(16)));
}
