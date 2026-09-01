import api from './http'

export interface UserProfile {
  nickName: string
  phonenumber: string
  email: string
  sex: string
}

export interface UserPassword {
  oldPassword: string
  newPassword: string
}

/** 獲取當前用戶個人資料 */
export function getUserProfile() {
  return api.get<UserProfile>('/api/v1/system/user/profile')
}

/** 更新當前用戶個人資料（暱稱、手機、郵箱、性別） */
export function updateUserProfile(data: UserProfile) {
  return api.put<{ ok: boolean }>('/api/v1/system/user/profile', data)
}

/** 修改當前用戶密碼 */
export function updateUserPwd(oldPassword: string, newPassword: string) {
  return api.put<{ ok: boolean }>('/api/v1/system/user/profile/password', {
    oldPassword,
    newPassword,
  })
}
