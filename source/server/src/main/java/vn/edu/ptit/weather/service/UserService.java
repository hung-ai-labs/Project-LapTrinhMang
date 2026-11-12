package vn.edu.ptit.weather.service;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import vn.edu.ptit.weather.dto.GeographyDto.*;
import vn.edu.ptit.weather.entity.User;
import vn.edu.ptit.weather.repository.UserRepository;

@Service
@RequiredArgsConstructor
public class UserService {
  private final AuthService auth;
  private final GeographyService geography;
  private final UserRepository users;

  public AddressResponse address() {
    return address(auth.currentUser());
  }

  private AddressResponse address(User user) {
    var ward =
        user.getDefaultWardId() == null ? null : geography.savedWard(user.getDefaultWardId());
    var parent = ward == null ? null : geography.savedProvince(ward.getProvinceId());
    return new AddressResponse(
        user.getAddressText(),
        ward == null ? null : WardResponse.from(ward),
        parent == null ? null : ProvinceResponse.from(parent));
  }

  @Transactional
  public AddressResponse save(AddressRequest request) {
    geography.ward(request.wardId());
    User user = auth.currentUser();
    user.setDefaultWardId(request.wardId());
    user.setAddressText(
        request.addressText() == null || request.addressText().isBlank()
            ? null
            : request.addressText().trim());
    users.save(user);
    return address(user);
  }

  @Transactional
  public AddressResponse delete() {
    User user = auth.currentUser();
    user.setDefaultWardId(null);
    user.setAddressText(null);
    users.save(user);
    return address(user);
  }
}
