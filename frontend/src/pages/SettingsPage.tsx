import { Topbar } from '../components/Topbar'
import { useMe } from '../features/auth/useMe'
import { DeleteAccountSection } from '../features/auth/DeleteAccountSection'
import { accountDeletionAvailable } from '../api/capabilities'

export function SettingsPage() {
  const me = useMe()
  return (
    <>
      <Topbar />
      <main className="settings-page">
        <header className="settings-intro">
          <h1>Cài đặt</h1>
          <p>Quản lý tài khoản và dữ liệu cuộc họp của bạn.</p>
        </header>
        <section
          className="settings-section"
          aria-labelledby="account-profile-heading"
        >
          <h2 id="account-profile-heading">Thông tin tài khoản</h2>
          <dl className="settings-profile">
            <div>
              <dt>Tên hiển thị</dt>
              <dd>{me.data?.user.display_name || 'Chưa có tên'}</dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd>{me.data?.user.email}</dd>
            </div>
          </dl>
        </section>
        {me.data && (
          <DeleteAccountSection
            email={me.data.user.email}
            available={accountDeletionAvailable}
          />
        )}
      </main>
    </>
  )
}
