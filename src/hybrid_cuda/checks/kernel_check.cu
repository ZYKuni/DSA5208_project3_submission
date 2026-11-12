#include "../kernels.cuh"
#include <iostream>
#include <vector>

namespace pcg {
void verify(int dim) {
    Tile t{23, 17, dim == 2 ? 1 : 5};
    const auto n = t.size();
    std::vector<double> input(std::size_t(t.nx + 2) * (t.ny + 2) * (t.nz + 2)), output(n);
    // Non-eigenmode data and nonzero ghosts expose stride and boundary mistakes.
    for (std::size_t i = 0; i < input.size(); ++i)
        input[i] = int((i * i + 3 * i) % 31) - 15;
    Buffer p(input.size()), ap(n), partial(blocks(n)), result(1);
    check(cudaMemcpy(p.ptr, input.data(), input.size() * sizeof(double), cudaMemcpyHostToDevice));
    stencil<<<blocks(n), width>>>(t, dim, n, 2, p.ptr, ap.ptr);
    check(cudaMemcpy(output.data(), ap.ptr, n * sizeof(double), cudaMemcpyDeviceToHost));
    double expected = 0;
    for (int z = 1; z <= t.nz; ++z)
        for (int y = 1; y <= t.ny; ++y)
            for (int x = 1; x <= t.nx; ++x) {
                auto value = [&](int k, int j, int i) {
                    return input[(k * (t.ny + 2) + j) * (t.nx + 2) + i];
                };
                double v = 2 * dim * value(z, y, x) - value(z, y, x - 1) - value(z, y, x + 1) -
                           value(z, y - 1, x) - value(z, y + 1, x);
                if (dim == 3)
                    v -= value(z - 1, y, x) + value(z + 1, y, x);
                if (output[((z - 1) * t.ny + y - 1) * t.nx + x - 1] != 2 * v)
                    throw std::runtime_error("stencil mismatch");
                expected += 2 * v * value(z, y, x);
            }
    dot<<<blocks(n), width>>>(t, n, p.ptr, ap.ptr, true, partial.ptr);
    dot<<<1, width>>>(t, blocks(n), partial.ptr, nullptr, false, result.ptr);
    double actual;
    check(cudaMemcpy(&actual, result.ptr, sizeof(double), cudaMemcpyDeviceToHost));
    if (actual != expected)
        throw std::runtime_error("dot mismatch");
}
// An independent coordinate traversal defines face order and the exact ghost cells written.
void verify_faces(Tile t, int dim) {
    const int extent[] = {t.nz, t.ny, t.nx};
    auto offset = [&](int z, int y, int x) { return (z * (t.ny + 2) + y) * (t.nx + 2) + x; };
    const int volume = (t.nz + 2) * (t.ny + 2) * (t.nx + 2);
    std::vector<double> input(volume), actual(volume);
    for (int i = 0; i < volume; ++i)
        input[i] = i + 1;
    Buffer field(volume);
    for (int axis = 3 - dim; axis < 3; ++axis) {
        for (int side = 0; side < 2; ++side) {
            const int boundary = side ? extent[axis] : 1;
            const int ghost = side ? extent[axis] + 1 : 0;
            std::vector<double> expected_face, expected_field(input);
            int send_base = -1, recv_base = -1;
            for (int z = 1; z <= t.nz; ++z)
                for (int y = 1; y <= t.ny; ++y)
                    for (int x = 1; x <= t.nx; ++x) {
                        int coord[] = {z, y, x};
                        if (coord[axis] != boundary)
                            continue;
                        const int src = offset(z, y, x);
                        coord[axis] = ghost;
                        const int dst = offset(coord[0], coord[1], coord[2]);
                        if (expected_face.empty()) {
                            send_base = src;
                            recv_base = dst;
                        }
                        expected_face.push_back(input[src]);
                        expected_field[dst] = input[src];
                    }
            const auto count = expected_face.size();
            Buffer packed(count);
            std::vector<double> face(count);
            check(cudaMemcpy(field.ptr, input.data(), volume * sizeof(double),
                             cudaMemcpyHostToDevice));
            face_copy<<<blocks(count), width>>>(t, axis, count, send_base, field.ptr, packed.ptr,
                                                false);
            check(cudaMemcpy(face.data(), packed.ptr, count * sizeof(double),
                             cudaMemcpyDeviceToHost));
            if (face != expected_face)
                throw std::runtime_error("face pack order mismatch");
            face_copy<<<blocks(count), width>>>(t, axis, count, recv_base, field.ptr, packed.ptr,
                                                true);
            check(cudaMemcpy(actual.data(), field.ptr, volume * sizeof(double),
                             cudaMemcpyDeviceToHost));
            if (actual != expected_field)
                throw std::runtime_error("ghost face or adjacent cells mismatch");
        }
    }
}
} // namespace pcg
int main() {
    pcg::verify(2);
    pcg::verify(3);
    pcg::verify_faces({23, 17, 1}, 2);
    pcg::verify_faces({23, 17, 5}, 3);
    std::cout << "2D and 3D GPU stencil and dot checks passed\n";
    std::cout << "GPU halo face packing and unpacking checks passed\n";
}
