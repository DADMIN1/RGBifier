#include <iostream>
#include <format>
#include <vector>
#include <filesystem>

#include <Magick++.h>
//#include <magick/MagickCore.h>


extern "C" { // libRGBmagick.so exports //
void PythonPlz(const wchar_t ezString[]) { // easy for python, that is. python strings are UTF8 (wchar_t)
	std::cout << "\r"; // something must be written to std::cout before ever using std::wcout; otherwise,
	// output will never appear on std::cout!! (affects everything; executable and shared-library/FFI.py)
	std::wcout << L"  [PythonPlz]: " << ezString << std::endl;
}

int EpicFunction(int argc, const char* argv[]) {
	for (int C{0}; C < argc; C++) {
		std::cout << "  [EpicFunction]: ";
		std::cout << C << ": " << argv[C] << '\n';
	}
	return 420;
}

// TODO: integrate into FFI.py
std::vector<Magick::Image> LoadImages(int argc, const char* argv[]) {
	std::vector<Magick::Image> imageList{}; imageList.reserve(1000);
	try { for (int C{0}; C < argc; ++C) { imageList.push_back(Magick::Image(argv[C])); }}
	catch (Magick::Exception& error) { std::cout << "[ERROR]" << error.what() << '\n'; }
	return imageList;
}

const char* GetImageSize(const char imagepath[]) {
	static std::string _ImageSizeString{"[0x0]"};
	try { Magick::Image testimage(imagepath); testimage.verbose(true);
		_ImageSizeString = std::format("[{}x{}]", testimage.columns(), testimage.rows());
	} catch (Magick::ErrorBlob& error){ _ImageSizeString = std::format("[ERROR] {}", error.what());}
	return _ImageSizeString.c_str();
}

}// extern "C"


// Magick::readImages doesn't accept format-specifiers ("frame%03d.png"); image sequences must be loaded manually
std::vector<Magick::Image> LoadImageDirectory(std::string directory) {
	std::vector<Magick::Image> imageList{}; imageList.reserve(360);
	// this iterates the directory in REVERSE order!?
	for(std::filesystem::directory_entry const& file: 
		std::filesystem::directory_iterator{directory}) {
		Magick::Image& newimg{imageList.emplace_back(file.path())}; newimg.trim( );
		std::string info = std::format("[{}x{}]", newimg.columns(), newimg.rows());
		std::cout << "loading: " << file.path().filename() << ": " << info << '\n'; // TODO: debug toggle
	}
	std::cout << std::format("loaded '{}' [{} images]", directory, imageList.size()) << '\n';
	return imageList;
}
// TODO: need to filter out the '.cache' files when loading MPC-frames
// if (file.path().extension() == ".mpc")

void ImageGrid(std::vector<Magick::Image>& imagelist, int stacklength, bool vert, std::string pfixstr)
{   // vertical image ordering stacks columns first, each stacklength-tall, then combines horizontally
	std::vector<Magick::Image> stacks{}; stacks.reserve(64);
	// segfaults if framestacks aren't all the same length
	if ((imagelist.size() % stacklength) != 0) {
		std::cout << std::format(
			"[WARNING] imagelist[{}] is not divisible by stacksize: {}[+{}]",
			imagelist.size(), stacklength, (imagelist.size() % stacklength)
		) << '\n';
		for (auto rem{(imagelist.size() % stacklength)}; rem > 0; --rem)
			imagelist.pop_back(); // resize until evenly divisible
		std::cout << "new length: " << imagelist.size() << '\n';
	}
	
	for(auto iter {imagelist.rbegin()}; iter < imagelist.rend();) {
	/*	std::cout << "next stack: " << iter->fileName() << '\n'; */
		Magick::Image& stacked{stacks.emplace_back()};
		Magick::appendImages(&stacked, iter, iter+stacklength, vert); // vertical
		//stacked.scale("5%"); // TODO: parameter. also should encode in filename
		iter += stacklength;
	}
	
	Magick::Image framegrid{};
	const auto stacksz_rows = (vert? stacklength : stacks.size());
	const auto stacksz_cols = (vert? stacks.size() : stacklength);
	Magick::appendImages(&framegrid, stacks.begin(), stacks.end(), !vert); // horizontal
	framegrid.repage(); // updating pagesize to new image geometry; extremely important!
	
	std::string filename = std::format("_{}{}_image_grid_[{}x{}].png",
		(vert?'V':'H'), imagelist.size(), stacksz_cols, stacksz_rows);
	std::string outpath{"/tmp/RGB_TOPLEVEL/output/"+pfixstr+filename};
	std::cout << std::format("{}_grid[{}x{}]({}x{} pixels): {}\n",((vert)? 'V':'H'),
		stacksz_cols, stacksz_rows, framegrid.columns(), framegrid.rows(), outpath);
	
	framegrid.write("PNG:"+outpath);
	return;
}


// stripped from library //
#ifndef IS_LIBRARY_BUILD
void PrintBuildInfo() {
	std::cout << "RGBmagick!!!";
	#ifdef MAGICKCORE_QUANTUM_DEPTH
	std::cout << " [QUANTUM_DEPTH: " << MAGICKCORE_QUANTUM_DEPTH << ']';
	#endif
	std::cout << '\n';
	
	#if MAGICKCORE_HDRI_ENABLE
	std::cout << "HDRI support enabled!!!\n";
	#endif
	
	#ifdef MAGICKCORE_MODULES_RELATIVE_PATH
	// I think this and a few other variables in "magick-config.h" should be defined...
	std::cout << "MAGICKCORE_MODULES_RELATIVE_PATH: " << MAGICKCORE_MODULES_RELATIVE_PATH << '\n';
	#endif
}

int main(int argc, const char* argv[])
{
	PrintBuildInfo();
	std::cout << "argc: " << argc << '\n';
	for (int C{0}; C < argc; C++) {
		std::cout << C << ": ";
		std::cout << argv[C] << '\n';
	}
	
	// ImageMagick will write temp/cache files to the current directory if TEMP_IM doesn't exist
	std::vector<std::filesystem::directory_entry> tempdirs {
		std::filesystem::directory_entry{"/tmp/RGB_TOPLEVEL/TEMP_IM/"},
		std::filesystem::directory_entry{"/tmp/RGB_TOPLEVEL/TEMP_GM/"},
		std::filesystem::directory_entry{"/tmp/RGB_TOPLEVEL/inputs/"},
		std::filesystem::directory_entry{"/tmp/RGB_TOPLEVEL/output/"},
	}; for (const std::filesystem::directory_entry& path: tempdirs) {
		if (!path.exists()) std::filesystem::create_directory(path);
	}
	
	std::cout << '\n';
	PythonPlz(L"Plz Print This WideString Plz C++");
	EpicFunction(argc, argv);
	std::cout << '\n';
	
	std::cout << "testimages/peach.png\n";
	Magick::Image testimage("testimages/peach.png");
	std::cout << testimage.magick() << '\n'; // PNG
	std::cout << GetImageSize("testimages/peach.png") << '\n';
	std::cout << '[' << testimage.columns() << 'x' << testimage.rows() << "]\n";
	std::cout << std::endl;
	
	// ImageGrid inputs
	std::string name{"peach"};
	std::string input_path{"/tmp/RGB_TOPLEVEL/png_frames_200"};
	int tile_width{420}; int tile_height{640}; // dimensions of the input-image
	std::string prefix = std::format("{}[{}x{}]", name, tile_width, tile_height);
	
	std::vector<Magick::Image> imagelist; imagelist.reserve(360);
	try { imagelist = LoadImageDirectory(input_path); }
	catch (Magick::Error& failed) {
		std::cout << "[ERROR] LoadImageDirectory: " << failed.what() << '\n';
		return 1;
	}
	
	for (bool vert: {false, true})
	{
		try { // TODO: generate symmetric divisors!
			ImageGrid(imagelist,  4, vert, prefix);
			ImageGrid(imagelist,  5, vert, prefix);
			ImageGrid(imagelist,  8, vert, prefix); // 200-frames only 
			ImageGrid(imagelist, 10, vert, prefix);
			ImageGrid(imagelist, 20, vert, prefix);
			ImageGrid(imagelist, 25, vert, prefix);
		} catch (Magick::Error& failed) {
			std::cout << "[ERROR] ImageGrid: " << failed.what() << '\n';
			return 2;
		}
	}
	return 0;
}

#endif //NOT_LIBRARY_BUILD
